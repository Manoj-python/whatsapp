import os
import json
import uuid
import time
import requests
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse, HttpResponseBadRequest, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db.models import Max

from .forms import UploadForm
from .models import SmsWhatsAppLog, BulkJob
from .tasks import process_bulk_whatsapp
from .utils import format_mobile


# ----------------------------------------------------------
# Helper: Send plain text message via WhatsApp Cloud API
# ----------------------------------------------------------
def send_whatsapp_text(to_number, text_body):
    """
    Sends a plain text message using WhatsApp Cloud API.
    """
    access_token = settings.WHATSAPP_ACCESS_TOKEN
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    if not access_token or not phone_number_id:
        raise RuntimeError("Set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in settings.py")

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_body},
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ----------------------------------------------------------
# Upload Excel + Trigger WhatsApp Bulk Sending
# ----------------------------------------------------------
def upload_and_send(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            choice = form.cleaned_data["template_choice"]
            excel_file = request.FILES["excel_file"]

            fs = FileSystemStorage(location="uploads/")
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)

            df = pd.read_excel(file_path, dtype=str).fillna("")
            total_customers = len(df)

            job_id = str(uuid.uuid4())
            job = BulkJob.objects.create(
                job_id=job_id,
                template_name=choice,
                total_customers=total_customers,
                excel_file=f"uploads/{filename}",
                status="Pending",
            )

            process_bulk_whatsapp.delay(file_path, choice, job_id)
            return redirect("job_status", job_id=job_id)
    else:
        form = UploadForm()

    return render(request, "messaging/index.html", {"form": form})


# ----------------------------------------------------------
# Job Status Page
# ----------------------------------------------------------
def job_status(request, job_id):
    job = get_object_or_404(BulkJob, job_id=job_id)
    progress = 0
    if job.total_customers > 0:
        progress = round((job.sent_count / job.total_customers) * 100, 2)
    return render(request, "messaging/job_status.html", {"job": job, "progress": progress})


# ----------------------------------------------------------
# Download Reports
# ----------------------------------------------------------
def download_success_report(request, job_id):
    file_path = "success_report.xlsx"
    if os.path.exists(file_path):
        return FileResponse(open(file_path, "rb"), as_attachment=True, filename=f"success_report_{job_id}.xlsx")
    raise Http404("Success report not found.")


def download_failed_report(request, job_id):
    file_path = "failed_report.xlsx"
    if os.path.exists(file_path):
        return FileResponse(open(file_path, "rb"), as_attachment=True, filename=f"failed_report_{job_id}.xlsx")
    raise Http404("Failed report not found.")

from django.conf import settings
# ----------------------------------------------------------
# Chat Dashboard
# ----------------------------------------------------------



# ----------------------------------------------------------
# Chat Dashboard
# ----------------------------------------------------------
def chat_dashboard(request):
    """
    Renders the chat dashboard with contact list and MEDIA_URL.
    """
    mobiles = (
        SmsWhatsAppLog.objects
        .values("mobile")
        .annotate(last_sent=Max("sent_at"))
        .order_by("-last_sent")
    )

    seen = set()
    mobile_list = []
    for m in mobiles:
        normalized = format_mobile(str(m["mobile"]))
        if normalized not in seen:
            seen.add(normalized)
            mobile_list.append({"mobile": normalized})

    return render(request, "messaging/chat.html", {
        "mobile_list": mobile_list,
        "MEDIA_URL": settings.MEDIA_URL,  # for JS rendering
    })


# ----------------------------------------------------------
# Fetch Messages (AJAX)
# ----------------------------------------------------------
def chat_messages_api(request, mobile):
    """
    Returns all messages (sent & received) for the given mobile number.
    Includes proper media URLs for image, video, audio, and document types.
    """
    normalized = format_mobile(str(mobile))
    messages_qs = SmsWhatsAppLog.objects.filter(mobile=normalized).order_by("sent_at")

    messages = []
    for msg in messages_qs:
        # ✅ Use Django's built-in file URL handling
        media_url = msg.media_file.url if msg.media_file else ""

        # Clean up message placeholder for media
        display_text = msg.sent_text_message or ""
        if display_text.startswith("[Image received"):
            display_text = "📷 Image"
        elif display_text.startswith("[Audio"):
            display_text = "🎧 Audio"
        elif display_text.startswith("[Video"):
            display_text = "🎬 Video"
        elif display_text.startswith("[Document"):
            display_text = "📄 Document"

        messages.append({
            "id": msg.id,
            "customer_name": msg.customer_name,
            "mobile": msg.mobile,
            "sent_text_message": display_text,
            "message_type": msg.message_type,
            "sent_at": msg.sent_at,
            "message_id": msg.message_id,
            "content_type": msg.content_type or "text",
            "media_file": media_url,  # ✅ Correct public URL
        })

    return JsonResponse({"messages": messages})
# ----------------------------------------------------------
# Send Reply (AJAX)
# ----------------------------------------------------------
@csrf_exempt
def send_reply_api(request):
    """
    Expects JSON: {"mobile": "+911234...", "text": "Reply"}
    Sends via WhatsApp API and logs it in SmsWhatsAppLog.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required.")

    try:
        payload = json.loads(request.body.decode("utf-8"))
        mobile = str(payload.get("mobile", "")).strip()
        text = payload.get("text", "").strip()

        if not mobile or not text:
            return HttpResponseBadRequest("mobile and text required.")

        # ✅ Always normalize
        mobile = format_mobile(mobile)

        api_resp = send_whatsapp_text(mobile, text)

        msg_id = ""
        if isinstance(api_resp, dict) and "messages" in api_resp and api_resp["messages"]:
            msg_id = api_resp["messages"][0].get("id", "")

        SmsWhatsAppLog.objects.create(
            customer_name="",
            mobile=mobile,
            template_name="manual",
            sent_text_message=text,
            status="Delivered" if msg_id else "Sent",
            message_id=msg_id,
            message_type="Sent",
        )
        return JsonResponse({"status": "ok", "api_response": api_resp})

    except requests.HTTPError as e:
        return JsonResponse({"error": "HTTP error", "detail": str(e)}, status=500)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ----------------------------------------------------------
# Webhook: Incoming Messages
# ----------------------------------------------------------
import os
import json
import requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.base import ContentFile
from .models import SmsWhatsAppLog
from .utils import format_mobile


@csrf_exempt
def whatsapp_webhook(request):
    """
    Handles WhatsApp Cloud API Webhook:
    - Text, Interactive, Image, Document, Audio, Video messages
    """
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == getattr(settings, "WHATSAPP_VERIFY_TOKEN", ""):
            return JsonResponse({"hub.challenge": challenge})
        return HttpResponseBadRequest("Invalid verification.")

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            entries = data.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    contacts = value.get("contacts", [])

                    for msg in messages:
                        from_num = format_mobile(msg.get("from", ""))
                        msg_id = msg.get("id", "")
                        msg_type = msg.get("type", "text")
                        text_body = ""
                        content_type = "unknown"
                        media_file = None

                        # --- Text ---
                        if msg_type == "text":
                            text_body = msg["text"].get("body", "")
                            content_type = "text"

                        # --- Interactive (button or list reply) ---
                        elif msg_type == "interactive":
                            content_type = "interactive"
                            interactive = msg.get("interactive", {})
                            if interactive.get("type") == "button":
                                text_body = interactive["button"].get("text", "")
                            elif interactive.get("type") == "list_reply":
                                text_body = interactive["list_reply"].get("title", "")

                        # --- Image ---
                        elif msg_type == "image":
                            content_type = "image"
                            image_info = msg.get("image", {})
                            media_id = image_info.get("id")
                            text_body = f"[Image received: {media_id}]"
                            media_file = download_whatsapp_media(media_id)

                        # --- Document ---
                        elif msg_type == "document":
                            content_type = "document"
                            doc_info = msg.get("document", {})
                            media_id = doc_info.get("id")
                            text_body = doc_info.get("filename", "[Document]")
                            media_file = download_whatsapp_media(media_id)

                        # --- Video ---
                        elif msg_type == "video":
                            content_type = "video"
                            vid_info = msg.get("video", {})
                            media_id = vid_info.get("id")
                            text_body = "[Video]"
                            media_file = download_whatsapp_media(media_id)

                        # --- Audio ---
                        elif msg_type == "audio":
                            content_type = "audio"
                            aud_info = msg.get("audio", {})
                            media_id = aud_info.get("id")
                            text_body = "[Audio]"
                            media_file = download_whatsapp_media(media_id)

                        # Save log
                        log = SmsWhatsAppLog.objects.create(
                            customer_name=(contacts[0].get("profile", {}).get("name") if contacts else ""),
                            mobile=from_num,
                            template_name="incoming",
                            sent_text_message=text_body,
                            status="Received",
                            message_type="Received",
                            message_id=msg_id,
                            content_type=content_type,
                        )

                        # Attach file if downloaded
                        if media_file:
                            filename, content = media_file
                            log.media_file.save(filename, ContentFile(content))
                            log.save()

            return JsonResponse({"status": "received"})

        except Exception as e:
            print("Webhook error:", e)
            return JsonResponse({"error": str(e)}, status=400)

    return HttpResponseBadRequest("Unsupported method.")


# ----------------------------------------------------------
# Helper: Download media from WhatsApp Cloud API
# ----------------------------------------------------------
def download_whatsapp_media(media_id):
    """
    Downloads media file from WhatsApp Cloud API using its media_id.
    Returns tuple: (filename, binary_content)
    """
    try:
        access_token = settings.WHATSAPP_ACCESS_TOKEN
        headers = {"Authorization": f"Bearer {access_token}"}

        # Step 1: get URL
        meta_url = f"https://graph.facebook.com/v17.0/{media_id}"
        meta_resp = requests.get(meta_url, headers=headers, timeout=30)
        meta_resp.raise_for_status()
        meta_data = meta_resp.json()
        file_url = meta_data.get("url")
        mime_type = meta_data.get("mime_type", "")
        extension = mime_type.split("/")[-1] if "/" in mime_type else "bin"

        # Step 2: download actual file
        file_resp = requests.get(file_url, headers=headers, timeout=30)
        file_resp.raise_for_status()
        filename = f"whatsapp_{media_id}.{extension}"

        return filename, file_resp.content

    except Exception as e:
        print("Failed to download media:", e)
        return None





import io
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from django.core.files.storage import default_storage
from .models import SmsWhatsAppLog


def export_received_messages_to_excel(request):
    """Export all received messages (text + image) to Excel."""
    # Create an in-memory workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Received Messages"

    # Headers
    ws.append(["Mobile", "Message", "Media (if image)"])

    # Filter only received messages
    logs = SmsWhatsAppLog.objects.filter(message_type="Received").order_by("-sent_at")

    for log in logs:
        mobile = log.mobile
        message = log.sent_text_message or ""

        # Default add row
        ws.append([mobile, message, ""])

        # If there’s an image, add it in the last column
        if log.media_file and log.content_type == "image":
            # Open the image file
            with default_storage.open(log.media_file.name, "rb") as f:
                img_data = io.BytesIO(f.read())
                img = ExcelImage(img_data)
                img.width = 100  # adjust size
                img.height = 100
                # place it in the same row, 3rd column (C)
                img_cell = f"C{ws.max_row}"
                ws.add_image(img, img_cell)

    # Set response headers
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="received_messages.xlsx"'

    # Save workbook to response
    wb.save(response)
    return response
