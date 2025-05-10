from apscheduler.schedulers.background import BackgroundScheduler
import threading
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import feedparser
import pytz
from pytz import UTC
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')


# ----- Existing logic (keywords + region filtering) -----

CONFLICT_KEYWORDS = [
    "conflict", "border", "strike", "attack", "missile", "drone", "war", "incursion",
    "ceasefire", "skirmish", "firing", "shelling", "militant", "terror", "tension",
    "army", "military", "airforce", "soldier", "deployment", "alert", "espionage",
    "LoC", "Line of Control", "cross-border", "surveillance", "aviation", "no-fly",
    "civilian flights", "airspace", "radar", "intelligence", "strike group", "navy",
    "India-Pakistan", "India Pakistan", "Pakistan India", "Indo-Pak", "Pakistani", "Indian",
    "Islamabad", "New Delhi", "Ministry of Defence", "defence", "IAF", "PAF",
    "prime minister", "statement", "diplomatic", "press conference", "official", "government",
    "external affairs", "spokesperson", "embassy", "security council", "UN response", "sindoor", "operation"
]
CONFLICT_KEYWORDS = [k.lower() for k in CONFLICT_KEYWORDS]  

INDIA_PAK_REGIONS = [
    "India", "Pakistan", "Jammu", "Kashmir", "Ladakh", "Punjab",
    "Islamabad", "Rawalpindi", "Karachi", "Srinagar", "New Delhi", "LoC", "Line of Control",
    "Indo-Pak", "India-Pakistan", "Pakistan-India", "IndoPak", "Pak-India", "India Pak"
]

def is_conflict_related(entry):
    content = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('link', '')}".lower()
    return any(keyword in content for keyword in CONFLICT_KEYWORDS)

def matches_region(text):
    text_lower = text.lower()
    return any(region.lower() in text_lower for region in INDIA_PAK_REGIONS)

# ----- Scraping Functions -----

def fetch_ndtv_latest():
    url = "https://www.ndtv.com/latest"
    soup = BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text, 'html.parser')
    articles = []
    for div in soup.select('div.new_storylising_content'):
        title_tag = div.select_one('h2')
        link_tag = div.select_one('a')
        if not title_tag or not link_tag:
            continue
        title = title_tag.text.strip()
        link = link_tag['href']
        summary = div.select_one('p').text.strip() if div.select_one('p') else ''
        articles.append({"title": title, "summary": summary, "link": link, "source": "NDTV", "timestamp": datetime.utcnow().replace(tzinfo=UTC)})
    return articles

def fetch_ani_latest():
    url = "https://www.aninews.in/category/national/"
    soup = BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text, 'html.parser')
    articles = []
    for card in soup.select('div.content'):
        a = card.find('a')
        if not a:
            continue
        title = a.text.strip()
        link = "https://www.aninews.in/category/national/" + a['href']
        articles.append({"title": title, "summary": '', "link": link, "source": "ANI", "timestamp": datetime.utcnow().replace(tzinfo=UTC)})
    return articles

def fetch_bbc_latest():
    url = "https://www.bbc.com/news/world/asia/india"
    soup = BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text, 'html.parser')
    articles = []
    for item in soup.select('a.gs-c-promo-heading'):
        title = item.text.strip()
        link = "https://www.bbc.com" + item['href']
        articles.append({"title": title, "summary": '', "link": link, "source": "BBC", "timestamp": datetime.utcnow().replace(tzinfo=UTC)})
    return articles

def fetch_aljazeera_latest():
    url = "https://www.aljazeera.com/news"
    soup = BeautifulSoup(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text, 'html.parser')
    articles = []
    for card in soup.select('article a.u-clickable-card__link'):
        title = card.text.strip()
        link = "https://www.aljazeera.com" + card['href']
        articles.append({"title": title, "summary": '', "link": link, "source": "Al Jazeera", "timestamp": datetime.utcnow().replace(tzinfo=UTC)})
    return articles

def fetch_google_news_latest():
    url = "https://news.google.com/rss/search?q=india+pakistan+conflict&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        summary = BeautifulSoup(entry.description, 'html.parser').get_text()
        source = entry.source.get('title', 'Unknown')
        timestamp = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=pytz.UTC)
        articles.append({
            'title': title,
            'summary': summary,
            'link': link,
            'source': source,
            'timestamp': timestamp
        })
    return articles

def get_headless_driver(debug=False):
    options = Options()
    if not debug:
        options.add_argument("--headless=new")  # Modern headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def scrape_latest_tweet(handle="PIB_India", max_tweets=2, debug=False):
    driver = get_headless_driver(debug=debug)
    results = []

    try:
        profile_url = f"https://twitter.com/{handle}"
        driver.get(profile_url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")

        tweet_links = []
        for a in soup.select("a[href*='/status/']"):
            href = a.get("href")
            if re.match(rf"^/{handle}/status/\d+$", href):
                tweet_links.append(href)

        unique_links = list(dict.fromkeys(tweet_links))[:max_tweets]
        print("Unique tweet links:", unique_links)

        for tweet_path in unique_links:
            tweet_url = f"https://twitter.com{tweet_path}"
            driver.get(tweet_url)
            time.sleep(3)

            tweet_soup = BeautifulSoup(driver.page_source, "html.parser")
            tweet_text_div = tweet_soup.find("div", attrs={"data-testid": "tweetText"})
            tweet_text = tweet_text_div.get_text(separator=" ").strip() if tweet_text_div else ""

            if not any(keyword in tweet_text.lower() for keyword in CONFLICT_KEYWORDS):
                continue

            time_tag = tweet_soup.find("time")
            if time_tag and time_tag.has_attr("datetime"):
                timestamp = datetime.strptime(
                    time_tag["datetime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                ).replace(tzinfo=pytz.UTC)
            else:
                timestamp = datetime.now(pytz.UTC)

            results.append({
                "title": f"@{handle} Tweeted ",
                "summary": tweet_text,
                "link": tweet_url,
                "source": "x.com",
                "timestamp": timestamp
            })

        return results

    finally:
        driver.quit()

def fetch_rss_feeds():
    RSS_FEEDS = {
        "BBC": "http://feeds.bbci.co.uk/news/world/south_asia/rss.xml",
        "ANI": "https://aninews.in/rss/national-news/",
        "NDTV": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "PIB": "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
    }
    articles = []
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            title = entry.title
            summary = entry.summary if hasattr(entry, 'summary') else ''
            if hasattr(entry, 'published_parsed'):
                timestamp = datetime(*entry.published_parsed[:6], tzinfo=pytz.UTC)
            else:
                timestamp = datetime.utcnow().replace(tzinfo=pytz.UTC)
            articles.append({
                "title": title,
                "summary": summary,
                "link": entry.link,
                "source": source,
                "timestamp": timestamp
            })
    return articles

def save_to_sqlite(filtered, db="crisis_feed.db"):
    import pandas as pd
    import sqlite3
    df = pd.DataFrame(filtered)
    df.drop_duplicates(subset=["link"], inplace=True)
    conn = sqlite3.connect(db)
    df.to_sql("feed", conn, if_exists="append", index=False)
    conn.execute("DELETE FROM feed WHERE rowid NOT IN (SELECT MIN(rowid) FROM feed GROUP BY link)")
    conn.commit()
    conn.close()

def load_from_sqlite(db="crisis_feed.db"):
    import pandas as pd
    import sqlite3
    conn = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM feed ORDER BY timestamp DESC", conn, parse_dates=["timestamp"])
    conn.close()
    return df.to_dict("records")


# ---- Scheduler and periodic fetch/store logic ----

def fetch_news_and_store():
    logging.info("⏳ Starting news fetch...")
    all_news = (
        fetch_rss_feeds() +
        fetch_ndtv_latest() +
        fetch_ani_latest() +
        fetch_bbc_latest() +
        fetch_google_news_latest()
    )
    filtered_news = [
        item for item in all_news
        if is_conflict_related(item) and matches_region(item['title'] + item['summary'])
    ]
    for item in filtered_news:
        if item['timestamp'].tzinfo is None:
            item['timestamp'] = item['timestamp'].replace(tzinfo=UTC)
        item['timestamp'] = item['timestamp'].astimezone(pytz.timezone('Asia/Kolkata'))
    save_to_sqlite(filtered_news)
    logging.info(f"✅ Saved {len(filtered_news)} news articles to database.")

def fetch_tweets_and_store():
    logging.info("⏳ Starting tweet fetch...")
    all_tweets = []
    for handle in ["PIB_India", "MEAIndia", "DefenceMinIndia", "adgpi", "PMOIndia", "SpokespersonMoD", "PIBFactCheck"]:
        try:
            tweets = scrape_latest_tweet(handle)
            all_tweets.extend(tweets)
        except Exception as e:
            logging.warning(f"❌ Failed to fetch tweets for {handle}: {e}")
    filtered_tweets = [
        item for item in all_tweets
        if is_conflict_related(item) and matches_region(item['title'] + item['summary'])
    ]
    for item in filtered_tweets:
        if item['timestamp'].tzinfo is None:
            item['timestamp'] = item['timestamp'].replace(tzinfo=UTC)
        item['timestamp'] = item['timestamp'].astimezone(pytz.timezone('Asia/Kolkata'))
    save_to_sqlite(filtered_tweets)
    logging.info(f"✅ Saved {len(filtered_tweets)} tweets to database.")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_news_and_store, 'interval', minutes=2, id='news_job')
    scheduler.add_job(fetch_tweets_and_store, 'interval', minutes=30, id='tweet_job')
    scheduler.start()
    logging.info("✅ Scheduler started: News every 2 mins, Tweets every 30 mins")

scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
scheduler_thread.start()

def get_all_combined_feeds():
    return load_from_sqlite()
