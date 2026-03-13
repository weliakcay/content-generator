from __future__ import annotations

from datetime import datetime
from utils.logger import get_logger
from mailer.email_sender import EmailSender

logger = get_logger("pin_email")

DAY_NAMES = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba",
    3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar",
}

MONTH_NAMES = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
    5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
    9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}


def build_pin_email_html(pin: dict) -> str:
    """Build HTML email for daily pin."""
    date = datetime.now()
    date_str = f"{date.day} {MONTH_NAMES[date.month]} {date.year}, {DAY_NAMES[date.weekday()]}"
    colors = pin.get("palette_colors", {})
    primary = colors.get("primary", "#7B3F72")
    secondary = colors.get("secondary", "#D4A5CC")
    accent = colors.get("accent", "#F5E0F0")

    hashtags_str = " ".join(pin.get("hashtags", []))
    tags_str = ", ".join(pin.get("pinterest_tags", []))
    special = pin.get("special_day")
    special_html = f'<div style="background:#FFF3CD;border:1px solid #FFEEBA;border-radius:8px;padding:12px;margin-bottom:16px;text-align:center;font-size:14px;">🎉 <strong>Özel Gün:</strong> {special}</div>' if special else ""

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:#F5F0F5;">

<div style="max-width:640px;margin:0 auto;background:#FFFFFF;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,{primary},{secondary});padding:32px 24px;text-align:center;">
    <div style="font-size:28px;margin-bottom:4px;">📌</div>
    <h1 style="color:#FFF;font-size:22px;margin:0;">WELLCO PINTEREST</h1>
    <p style="color:rgba(255,255,255,0.9);font-size:13px;margin:8px 0 0;">Günlük Pin İçeriği Hazır</p>
  </div>

  <!-- Date Bar -->
  <div style="background:{accent};padding:12px 24px;text-align:center;border-bottom:2px solid {secondary};">
    <span style="font-size:14px;color:{colors.get('text_dark', '#2D1B4E')};">📅 {date_str}</span>
  </div>

  <div style="padding:24px;">
    {special_html}

    <!-- Board & Style Info -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
      <tr>
        <td style="padding:8px 12px;background:#F8F4FB;border-radius:8px 8px 0 0;border-bottom:1px solid #EEE;">
          <strong>📋 Pano:</strong> {pin.get('board', '')}
        </td>
      </tr>
      <tr>
        <td style="padding:8px 12px;background:#F8F4FB;border-bottom:1px solid #EEE;">
          <strong>📅 Gün:</strong> {pin.get('day_name', '')} | <strong>Tema:</strong> {pin.get('theme', '')}
        </td>
      </tr>
      <tr>
        <td style="padding:8px 12px;background:#F8F4FB;border-bottom:1px solid #EEE;">
          <strong>🎨 Stil:</strong> {pin.get('style_code', '')} - {pin.get('style_name', '')}
        </td>
      </tr>
      <tr>
        <td style="padding:8px 12px;background:#F8F4FB;border-bottom:1px solid #EEE;">
          <strong>🎨 Palette:</strong> {pin.get('palette_code', '')} - {pin.get('palette_name', '')}
          <span style="display:inline-block;width:14px;height:14px;background:{primary};border-radius:3px;vertical-align:middle;margin-left:4px;"></span>
          <span style="display:inline-block;width:14px;height:14px;background:{secondary};border-radius:3px;vertical-align:middle;margin-left:2px;"></span>
          <span style="display:inline-block;width:14px;height:14px;background:{accent};border-radius:3px;vertical-align:middle;margin-left:2px;border:1px solid #DDD;"></span>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 12px;background:#F8F4FB;border-radius:0 0 8px 8px;">
          <strong>📐 Format:</strong> Standart 2:3 (1000x1500px)
        </td>
      </tr>
    </table>

    <!-- Pin Title -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">📝 Pin Başlığı</div>
      <div style="background:linear-gradient(135deg,{primary}10,{secondary}20);border-left:4px solid {primary};padding:14px 16px;border-radius:0 8px 8px 0;font-size:18px;font-weight:bold;color:#2D2D2D;">
        {pin.get('pin_title', '')}
      </div>
    </div>

    <!-- Description -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">📄 Pin Açıklaması <span style="background:#EEE;padding:2px 6px;border-radius:4px;font-size:10px;">{pin.get('description_length', 'ORTA')}</span></div>
      <div style="background:#FAFAFA;border:1px solid #EEE;border-radius:8px;padding:14px 16px;font-size:14px;line-height:1.6;color:#444;">
        {pin.get('pin_description', '')}
      </div>
    </div>

    <!-- Visual Prompt -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">🎨 Görsel Prompt (Midjourney/DALL-E)</div>
      <div style="background:#1A1A2E;border-radius:8px;padding:14px 16px;font-size:13px;line-height:1.6;color:#E0E0E0;font-family:'Courier New',monospace;word-break:break-word;">
        {pin.get('visual_prompt', '')}
      </div>
    </div>

    <!-- File Name -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">📁 Dosya Adı</div>
      <div style="background:#F0F0F0;border-radius:8px;padding:10px 16px;font-family:'Courier New',monospace;font-size:13px;color:#333;">
        {pin.get('file_name', '')}
      </div>
    </div>

    <!-- Alt Text -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">🏷️ Alt Text</div>
      <div style="background:#FAFAFA;border:1px solid #EEE;border-radius:8px;padding:10px 16px;font-size:13px;color:#555;">
        {pin.get('alt_text', '')}
      </div>
    </div>

    <!-- Hashtags -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">🏷️ Hashtag'ler</div>
      <div style="background:{accent};border-radius:8px;padding:10px 16px;font-size:13px;color:{colors.get('text_dark', '#2D1B4E')};">
        {hashtags_str}
      </div>
    </div>

    <!-- Pinterest Tags -->
    <div style="margin-bottom:20px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">🏷️ Pinterest Tag'leri</div>
      <div style="background:#F8F4FB;border-radius:8px;padding:10px 16px;font-size:13px;color:#555;">
        {tags_str}
      </div>
    </div>

    <!-- Posting Time -->
    <div style="margin-bottom:24px;">
      <div style="font-size:11px;text-transform:uppercase;color:#999;letter-spacing:1px;margin-bottom:6px;">⏰ Önerilen Paylaşım Zamanı</div>
      <div style="background:#E8F5E9;border-radius:8px;padding:10px 16px;font-size:14px;color:#2E7D32;font-weight:bold;">
        {pin.get('posting_time', '')}
      </div>
    </div>

    <!-- Next Steps -->
    <div style="background:linear-gradient(135deg,{primary}08,{secondary}15);border:1px solid {secondary};border-radius:12px;padding:20px;">
      <div style="font-size:14px;font-weight:bold;color:{colors.get('text_dark', '#2D1B4E')};margin-bottom:12px;">🎯 Sonraki Adımlar</div>
      <div style="font-size:13px;color:#555;line-height:1.8;">
        ✅ Görsel prompt'u kopyala<br>
        ✅ Midjourney/DALL-E'de çalıştır<br>
        ✅ Görseli indir (1000x1500px)<br>
        ✅ Dosya adını değiştir: <code style="background:#EEE;padding:1px 4px;border-radius:3px;font-size:12px;">{pin.get('file_name', '')}</code><br>
        ✅ Pinterest'e yükle → <strong>{pin.get('board', '')}</strong> panosuna<br>
        ✅ Başlık, açıklama, alt text'i yapıştır<br>
        ✅ Tag'leri ekle
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:{primary};padding:20px 24px;text-align:center;">
    <p style="color:rgba(255,255,255,0.8);font-size:12px;margin:0;">
      Dashboard: <a href="http://localhost:3000/pinterest" style="color:#FFF;">http://localhost:3000/pinterest</a>
    </p>
    <p style="color:rgba(255,255,255,0.6);font-size:11px;margin:8px 0 0;">💜 Wellco Adult Content Generator</p>
  </div>

</div>
</body>
</html>"""

    return html


def build_pin_email_text(pin: dict) -> str:
    """Build plain text version of pin email."""
    date = datetime.now()
    date_str = f"{date.day} {MONTH_NAMES[date.month]} {date.year}, {DAY_NAMES[date.weekday()]}"

    return f"""📌 WELLCO PINTEREST - GÜNLÜK PİN
{'='*60}
📋 PANO: {pin.get('board', '')}
📅 GÜN: {pin.get('day_name', '')} | TEMA: {pin.get('theme', '')}
🎨 STİL: {pin.get('style_code', '')} - {pin.get('style_name', '')}
🎨 PALETTE: {pin.get('palette_code', '')} - {pin.get('palette_name', '')}
📐 FORMAT: Standart 2:3 (1000x1500px)
{'='*60}

📝 PIN BAŞLIĞI:
{pin.get('pin_title', '')}
{'-'*60}

📄 PIN AÇIKLAMASI:
{pin.get('pin_description', '')}
{'-'*60}

🎨 GÖRSEL PROMPT (Midjourney/DALL-E):
{pin.get('visual_prompt', '')}
{'-'*60}

📁 DOSYA ADI:
{pin.get('file_name', '')}
{'-'*60}

🏷️ ALT TEXT:
{pin.get('alt_text', '')}
{'-'*60}

🏷️ HASHTAG'LER:
{' '.join(pin.get('hashtags', []))}

🏷️ PINTEREST TAG'LER:
{', '.join(pin.get('pinterest_tags', []))}

⏰ PAYLAŞIM ZAMANI: {pin.get('posting_time', '')}
{'='*60}

🎯 SONRAKI ADIMLAR:
✅ Görsel prompt'u kopyala
✅ Midjourney/DALL-E'de çalıştır
✅ Görseli indir (1000x1500px)
✅ Dosya adını değiştir
✅ Pinterest'e yükle
✅ Başlık, açıklama, alt text yapıştır
✅ Tag'leri ekle

Dashboard: http://localhost:3000/pinterest
{'='*60}
💜 Wellco Adult Content Generator
"""


def send_pin_email(pin: dict) -> bool:
    """Send daily pin email."""
    date = datetime.now()
    date_str = f"{date.day} {MONTH_NAMES[date.month]} {date.year}, {DAY_NAMES[date.weekday()]}"

    subject = f"Wellco Pinterest | {date_str} - Bugünün Pin'i Hazır 📌"
    html = build_pin_email_html(pin)
    text = build_pin_email_text(pin)

    sender = EmailSender()
    return sender.send(html_content=html, subject=subject)
