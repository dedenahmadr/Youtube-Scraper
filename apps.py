# youtube_comment_scraper_app.py

import streamlit as st
import pandas as pd
from datetime import datetime
from googleapiclient.discovery import build

# ========== KONFIGURASI API ==========
API_KEY = "AIzaSyD2zd-4T6_BB24z6XVQT-JIJu0bGOWuodE"  # Ganti dengan API Key YouTube kamu
youtube = build('youtube', 'v3', developerKey=API_KEY)

# ========== FUNGSI SCRAPING ==========

def get_channel_id_from_handle(handle):
    request = youtube.search().list(
        part="snippet",
        q=handle,
        type="channel",
        maxResults=1
    )
    response = request.execute()
    return response['items'][0]['snippet']['channelId']

def get_all_video_ids(channel_id, start_date=None, end_date=None):
    video_ids = []
    next_page_token = None

    while True:
        request = youtube.search().list(
            part='snippet',
            channelId=channel_id,
            maxResults=50,
            order='date',
            pageToken=next_page_token,
            type='video',
            publishedAfter=start_date.strftime("%Y-%m-%dT%H:%M:%SZ") if start_date else None,
            publishedBefore=end_date.strftime("%Y-%m-%dT%H:%M:%SZ") if end_date else None
        )
        response = request.execute()

        for item in response['items']:
            video_ids.append({
                'videoId': item['id']['videoId'],
                'publishedAt': item['snippet']['publishedAt'],
                'title': item['snippet']['title']
            })

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return video_ids

def get_video_comments(video_id, video_title=None):
    comments = []
    next_page_token = None

    while True:
        response = youtube.commentThreads().list(
            part='snippet,replies',
            videoId=video_id,
            maxResults=100,
            pageToken=next_page_token
        ).execute()

        for item in response['items']:
            top = item['snippet']['topLevelComment']['snippet']
            comments.append([
                top['publishedAt'],
                top['authorDisplayName'],
                top['textDisplay'],
                top['likeCount'],
                video_id,
                video_title if video_title else ""
            ])

            if item['snippet']['totalReplyCount'] > 0:
                for reply in item['replies']['comments']:
                    rep = reply['snippet']
                    comments.append([
                        rep['publishedAt'],
                        rep['authorDisplayName'],
                        rep['textDisplay'],
                        rep['likeCount'],
                        video_id,
                        video_title if video_title else ""
                    ])

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return comments

def get_comments_by_query(query):
    comments = []
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        type="video",
        maxResults=50
    ).execute()

    video_ids = []
    for item in search_response.get('items', []):
        video_ids.append({
            'videoId': item['id']['videoId'],
            'title': item['snippet']['title']
        })

    for video in video_ids:
        try:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video['videoId'],
                textFormat="plainText",
                maxResults=100
            ).execute()

            while response:
                for item in response.get("items", []):
                    comment = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append({
                        "video_id": video['videoId'],
                        "video_title": video['title'],
                        "comment": comment["textDisplay"],
                        "time": comment["publishedAt"],
                        "like_count": comment["likeCount"],
                        "author": comment["authorDisplayName"]
                    })

                if "nextPageToken" in response:
                    response = youtube.commentThreads().list(
                        part="snippet",
                        videoId=video['videoId'],
                        textFormat="plainText",
                        maxResults=100,
                        pageToken=response["nextPageToken"]
                    ).execute()
                else:
                    break
        except Exception as e:
            print(f"Error fetching comments for video {video['videoId']}: {e}")

    return comments

# ========== STREAMLIT APP ==========
st.set_page_config(page_title="YouTube Comment Scraper", layout="wide")
st.title("📺 YouTube Comment Scraper")
st.markdown("Scrape komentar YouTube berdasarkan Channel, Video, atau Pencarian Query.")

menu = st.sidebar.radio("Pilih Mode Scraping", ["Channel", "Video ID", "Query"])

if menu == "Channel":
    st.header("📌 Scrape Berdasarkan Channel Handle")
    channel_url = st.text_input("Masukkan URL Channel (misal: https://www.youtube.com/@MasTriAdhianto)")
    start = st.date_input("Tanggal Mulai", datetime(2025, 2, 1))
    end = st.date_input("Tanggal Akhir", datetime(2025, 5, 1))

    if st.button("Scrape Komentar"):
        with st.spinner("Mengambil data..."):
            handle = channel_url.split("/")[-1]
            try:
                channel_id = get_channel_id_from_handle(handle)
                videos = get_all_video_ids(channel_id, start, end)
                all_comments = []
                for video in videos:
                    all_comments.extend(get_video_comments(video["videoId"], video["title"]))
                df = pd.DataFrame(all_comments, columns=[
                    'publishedAt', 'authorDisplayName', 'textDisplay',
                    'likeCount', 'videoId', 'videoTitle'
                ])
                st.success(f"{len(df)} komentar berhasil diambil dari {len(videos)} video.")
                st.dataframe(df)
                st.download_button("Download CSV", df.to_csv(index=False), "comments_by_channel.csv")
            except Exception as e:
                st.error(f"Gagal: {e}")

elif menu == "Video ID":
    st.header("🎥 Scrape Berdasarkan Video ID")
    video_id = st.text_input("Masukkan Video ID (misal: kRAFVjC_fdI)")

    if st.button("Scrape Komentar Video"):
        with st.spinner("Mengambil komentar..."):
            try:
                comments = get_video_comments(video_id)
                df = pd.DataFrame(comments, columns=[
                    'publishedAt', 'authorDisplayName', 'textDisplay',
                    'likeCount', 'videoId', 'videoTitle'
                ])
                st.success(f"{len(df)} komentar berhasil diambil.")
                st.dataframe(df)
                st.download_button("Download CSV", df.to_csv(index=False), "comments_by_video.csv")
            except Exception as e:
                st.error(f"Gagal: {e}")

elif menu == "Query":
    st.header("🔍 Scrape Berdasarkan Pencarian Query")
    query = st.text_input("Masukkan Query (misal: banjir bekasi)")

    if st.button("Scrape Komentar dari Query"):
        with st.spinner("Mengambil komentar..."):
            try:
                results = get_comments_by_query(query)
                df = pd.DataFrame(results)
                if len(df) > 0:
                    st.success(f"{len(df)} komentar berhasil diambil.")
                    st.dataframe(df)
                    st.download_button("Download CSV", df.to_csv(index=False), "comments_by_query.csv")
                else:
                    st.warning("Tidak ada komentar yang ditemukan untuk query ini.")
            except Exception as e:
                st.error(f"Gagal: {e}")
