"""Test email sending with mock data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from generators.content_generator import ContentGenerator
from mailer.report_builder import ReportBuilder
from mailer.email_sender import EmailSender


def main():
    print("📧 Email test başlıyor...")

    # Generate mock suggestions
    generator = ContentGenerator()
    daily = generator._generate_mock_suggestions()

    from generators.suggestion_model import DailySuggestions
    from utils.date_utils import today_str
    mock_daily = DailySuggestions(date=today_str(), suggestions=daily)

    # Build report
    builder = ReportBuilder()
    html = builder.build(mock_daily)
    subject = builder.build_subject()

    # Save HTML locally for preview
    output_path = Path(__file__).parent.parent / "data" / "test_email.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ HTML rapor kaydedildi: {output_path}")
    print(f"   Tarayıcıda açın: file://{output_path.resolve()}")

    # Try sending
    sender = EmailSender()
    sent = sender.send(html, subject)

    if sent:
        print("✅ Email başarıyla gönderildi!")
    else:
        print("⚠️  Email gönderilemedi (SMTP ayarlarını kontrol edin)")
        print("   HTML dosyasını tarayıcıda açarak raporu görebilirsiniz")


if __name__ == "__main__":
    main()
