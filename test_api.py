from app import create_app
from app.extensions import db
from app.models import EnvironmentalNews
from app.utils.ai import fetch_environmental_news
from datetime import datetime

app = create_app()
with app.app_context():
    try:
        news_items = fetch_environmental_news()
        print("News Items:", news_items)
        if news_items:
            EnvironmentalNews.query.delete()
            for item in news_items:
                news_entry = EnvironmentalNews(
                    title=item['title'],
                    description=item['description'],
                    source=item.get('source', ''),
                    date_added=datetime.utcnow()
                )
                db.session.add(news_entry)
            db.session.commit()
            print("Successfully committed!")
    except Exception as e:
        print("Error during commit:", str(e))
        db.session.rollback()
    
    latest = EnvironmentalNews.query.all()
    print("DB contains:", len(latest))
