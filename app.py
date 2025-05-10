import streamlit as st
from feed_utils import load_from_sqlite, get_all_combined_feeds
from datetime import datetime, date

st.set_page_config(page_title="Crisis Update Feed", layout="wide")
st.title("🛰️ Indo-Pak Crisis Information Feed")

if st.button("🔄 Refresh Feed Now"):
    with st.spinner("Fetching fresh updates..."):
        get_all_combined_feeds()
    st.success("Feed updated!")

# Sidebar filters
st.sidebar.header("🗂️ Filters")
selected_date = st.sidebar.date_input("Select a date", date.today())
only_tweets = st.sidebar.checkbox("Show only tweets", value=False)
search_query = st.sidebar.text_input("🔍 Search keyword")

# if st.sidebar.button("🔄 Refresh Feed Now"):
#     with st.spinner("Fetching fresh updates..."):
#         get_all_combined_feeds()
#     st.success("Feed updated!")

# Load cached feed from SQLite
with st.spinner("Loading updates..."):
    posts = load_from_sqlite()

# Filter by date    
posts = [
    post for post in posts
    if post['timestamp'].date() == selected_date
]

# Filter by source (if only tweets)
if only_tweets:
    posts = [post for post in posts if post['source'].lower() == 'x.com']

if search_query:
    posts = [
        post for post in posts
        if search_query.lower() in post['title'].lower()
        or search_query.lower() in post['summary'].lower()
    ]

# Sort newest first
posts = sorted(posts, key=lambda x: x['timestamp'], reverse=True)


# Display
if posts:
    for post in posts:
        st.markdown(f"### {post['title']}")
        st.markdown(f"**Source:** {post['source']} &nbsp; | &nbsp; _{post['timestamp'].strftime('%Y-%m-%d %H:%M')}_")
        st.write(post['summary'])
        st.markdown(f"[Read more]({post['link']})", unsafe_allow_html=True)
        st.markdown("---")
else:
    st.info("No posts found for the selected filters.")