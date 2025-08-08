import streamlit as st
import streamlit.components.v1 as components
import pickle
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import ssl
import urllib3
import certifi
import os
import time

# Set page title and icon
st.set_page_config(
    page_title="Movie Recommender",
    page_icon="🎬",
    layout="wide",
)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure requests session with SSL handling and retry strategy
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    raise_on_status=False
)

# Configure adapter with retry strategy
adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=10,
    pool_maxsize=20,
    pool_block=False
)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Set timeout and headers
session.timeout = 30
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json',
    'Connection': 'keep-alive'
})

# Try different SSL approaches
try:
    # First, try using certifi certificates
    session.verify = certifi.where()
except Exception:
    try:
        # If that fails, try setting CA bundle from environment
        ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE') or os.environ.get('CURL_CA_BUNDLE')
        if ca_bundle:
            session.verify = ca_bundle
        else:
            # As a last resort, disable SSL verification
            session.verify = False
    except Exception:
        # Fallback: disable SSL verification
        session.verify = False

# Alternative session for fallback
fallback_session = requests.Session()
fallback_session.verify = False
fallback_session.timeout = 15
fallback_session.headers.update({
    'User-Agent': 'MovieRecommenderApp/1.0',
    'Accept': 'application/json'
})

import zlib

movies_dict = pickle.load(open('movie_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
with open('similarity_compressed.pkl', 'rb') as compressed_file:
    similarity = pickle.loads(zlib.decompress(compressed_file.read()))

# similarity = pickle.load(open('similarity.pkl', 'rb'))

# Sample API to fetch movie details
API_KEY = "df957ac8237d3d811c021c6112a49de2"

def make_api_request(url, use_fallback=False):
    """Helper function to make API requests with fallback options"""
    current_session = fallback_session if use_fallback else session
    max_retries = 2 if use_fallback else 3
    
    for attempt in range(max_retries):
        try:
            time.sleep(0.2 * (attempt + 1))  # Progressive delay
            response = current_session.get(url, timeout=20 if use_fallback else 30)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.ChunkedEncodingError,
                ConnectionResetError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 1.5
                if not use_fallback:
                    st.warning(f"Connection issue, retrying... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                if not use_fallback:
                    # Try with fallback session
                    st.info("Trying alternative connection method...")
                    return make_api_request(url, use_fallback=True)
                else:
                    raise e
        except requests.exceptions.RequestException as e:
            if not use_fallback and attempt == max_retries - 1:
                return make_api_request(url, use_fallback=True)
            elif use_fallback or attempt == max_retries - 1:
                raise e
    return None

def fetch_movie_details(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US"
        data = make_api_request(url)
        return data if data else {}
    except Exception as e:
        st.error(f"Error fetching movie details: {e}")
        return {}

def fetch_movie_credits(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={API_KEY}"
        data = make_api_request(url)
        return data if data else {'crew': [], 'cast': []}
    except Exception as e:
        st.error(f"Error fetching movie credits: {e}")
        return {'crew': [], 'cast': []}

def fetch_movie_videos(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={API_KEY}"
        data = make_api_request(url)
        return data if data else {'results': []}
    except Exception as e:
        st.error(f"Error fetching movie videos: {e}")
        return {'results': []}

def fetch_trending_movies():
    try:
        url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={API_KEY}"
        data = make_api_request(url)
        return data.get('results', []) if data else []
    except Exception as e:
        st.error(f"Error fetching trending movies: {e}")
        return []

def fetch_poster(movie_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US"
        data = make_api_request(url)
        if data and 'poster_path' in data and data['poster_path']:
            return "https://image.tmdb.org/t/p/w300/" + data['poster_path']
        else:
            return "https://via.placeholder.com/300x450?text=No+Image"
    except Exception as e:
        st.error(f"Error fetching poster: {e}")
        return "https://via.placeholder.com/300x450?text=No+Image"


def recommend(movie, num_recommendations,sort_by):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:num_recommendations+1]

    recommended_movies = []
    recommended_movies_posters = []
    recommended_release_dates = []
    recommended_ratings = []

    for i in movies_list:
        movie_id = movies.iloc[i[0]].movie_id
        movie_title = movies.iloc[i[0]].title
        
        # Fetch movie details with error handling
        movie_details = fetch_movie_details(movie_id)
        if movie_details:
            release_date = movie_details.get('release_date', 'Unknown')
            rating = movie_details.get('vote_average', 0)
        else:
            release_date = 'Unknown'
            rating = 0

        recommended_movies.append(movie_title)
        recommended_movies_posters.append(fetch_poster(movie_id))
        recommended_release_dates.append(release_date)
        recommended_ratings.append(rating)

    # Sort recommendations based on user's choice
    if sort_by == 'Release Date':
        sorted_movies = sorted(
            zip(recommended_movies, recommended_movies_posters, recommended_release_dates, recommended_ratings),
            key=lambda x: x[2], reverse=True)
    elif sort_by == 'Rating':
        sorted_movies = sorted(
            zip(recommended_movies, recommended_movies_posters, recommended_release_dates, recommended_ratings),
            key=lambda x: x[3], reverse=True)
    else:
        sorted_movies = sorted(
            zip(recommended_movies, recommended_movies_posters, recommended_release_dates, recommended_ratings),
            key=lambda x: x[0])

    sorted_recommendations, sorted_posters, sorted_release_dates, sorted_ratings = zip(*sorted_movies)
    return sorted_recommendations, sorted_posters, sorted_release_dates, sorted_ratings


# Set up the UI layout
st.title('Movie Recommender System')
st.sidebar.title('Menu')

# Movie selection with sorted options
movie_options = ["-- Choose a Movie --"] + sorted(movies['title'].values, key=lambda x: x.lower())

selected_movie_name = st.sidebar.selectbox(
    'Choose A Movie🎬:',
    movie_options
)

if selected_movie_name != "-- Choose a Movie --":
    # Your code to handle the selected movie
    st.write(f"You selected: {selected_movie_name}")

# Create a sidebar option to select between Recommendations and Ratings/Reviews
selected_option = st.sidebar.selectbox("Select Option", ["Recommendations", "Ratings/Reviews","Trending","Genre Filters"])

# Recommendation Section
if selected_option == "Recommendations":

    # Number of recommendations setting
    num_recommendations = st.sidebar.slider(
        'Number of Recommendations', 1, 5, 3)

    # Sorting options
    sorting_options = ['Title', 'Release Date', 'Rating']
    selected_sorting_option = st.sidebar.selectbox('Sort By:', sorting_options)

    if st.sidebar.button('Recommend'):
        names, posters, release_dates, ratings = recommend(selected_movie_name, num_recommendations, selected_sorting_option)
        # Display recommendations in columns
        columns = st.columns(num_recommendations)
        for i in range(num_recommendations):
            with columns[i]:
                st.image(posters[i], caption=names[i], use_column_width=True)
                st.write(f"Release Date: {release_dates[i]}")
                st.write(f"Rating: {ratings[i]}")

    # Display additional movie details and poster
    if selected_movie_name:
        try:
            movie_id = movies[movies['title'] == selected_movie_name]['movie_id'].values[0]
            movie_details = fetch_movie_details(movie_id)
            credits = fetch_movie_credits(movie_id)
            videos = fetch_movie_videos(movie_id)

            if movie_details:
                poster_url = fetch_poster(movie_details['id'])
                st.subheader(f"Details for {selected_movie_name}")
                st.image(poster_url, width=200)

                st.write(f"**Release Date:** {movie_details.get('release_date', 'Unknown')}")
                st.write(f"**Overview:** {movie_details.get('overview', 'No overview available')}")
                st.write(f"**Rating:** {movie_details.get('vote_average', 'N/A')}")
                st.write(f"**Runtime:** {movie_details.get('runtime', 'Unknown')} minutes")

                # Display director(s)
                directors = [crew['name'] for crew in credits.get('crew', []) if crew['job'] == 'Director']
                st.write(f"**Director(s):** {', '.join(directors) if directors else 'Unknown'}")

                # Display cast members
                cast = [cast_member['name'] for cast_member in credits.get('cast', [])[:10]]
                st.write(f"**Cast:** {', '.join(cast) if cast else 'Unknown'}")

                # Display movie trailers
                trailers = [video['name'] for video in videos.get('results', []) if video['site'] == 'YouTube']
                if trailers:
                    st.write("**Trailers:**")
                    for trailer_name in trailers:
                        trailer_key = next((video['key'] for video in videos['results'] if video['name'] == trailer_name), None)
                        if trailer_key:
                            st.write(f"[{trailer_name}](https://www.youtube.com/watch?v={trailer_key})")
        except Exception as e:
            st.error(f"Error displaying movie details: {e}")


# Ratings/Reviews section
elif selected_option == "Ratings/Reviews":
    st.sidebar.title('Rating and Review')

    # Dictionary to store user ratings and reviews
    @st.cache_resource
    def get_user_ratings_reviews():
        return {}

    user_ratings_reviews = get_user_ratings_reviews()

    # Allow users to rate and review the selected movie
    user_rating = st.sidebar.slider('Rate the Movie (1-5)', 1, 5, 3)
    user_review = st.sidebar.text_area('Write a Review (optional)')

    # Function to store user ratings and reviews
    def store_user_ratings_reviews(movie_name, rating, review):
        if movie_name not in user_ratings_reviews:
            user_ratings_reviews[movie_name] = []

        user_ratings_reviews[movie_name].append({'Rating': rating, 'Review': review})

    if st.sidebar.button('Submit'):
        store_user_ratings_reviews(selected_movie_name, user_rating, user_review)

    # Display user ratings and reviews for the selected movie
    if selected_movie_name in user_ratings_reviews:
        st.sidebar.subheader(f'Ratings and Reviews for {selected_movie_name}')
        for entry in user_ratings_reviews[selected_movie_name]:
            st.sidebar.write(f'**Rating:** {entry["Rating"]}')
            if entry['Review']:
                st.sidebar.write(f'**Review:** {entry["Review"]}')

    # Display stored user ratings and reviews in a separate tab
    if st.sidebar.button('View Ratings and Reviews'):
        st.title('Past User Ratings and Reviews')
        for movie_name, reviews in user_ratings_reviews.items():
            st.subheader(f'For {movie_name}')
            for entry in reviews:
                st.write(f'**Rating:** {entry["Rating"]}')
                if entry['Review']:
                    st.write(f'**Review:** {entry["Review"]}')

elif selected_option == "Trending":
    # Trending Movies section
    st.sidebar.title('Trending Movies')

    # Fetch and display trending movies
    trending_movies = fetch_trending_movies()

    if trending_movies:
        for movie in trending_movies:
            poster_url = fetch_poster(movie['id'])
            st.image(poster_url, caption=movie.get('title', 'Unknown Title'), width=200)
            st.write(f"**Release Date:** {movie.get('release_date', 'Unknown')}")
            st.write(f"**Overview:** {movie.get('overview', 'No overview available')}")
            st.write(f"**Rating:** {movie.get('vote_average', 'N/A')}")
    else:
        st.write("Unable to fetch trending movies at the moment.")

elif selected_option == "Genre Filters":

    with open("index.html", "r") as f:
        html_code = f.read()
    st.components.v1.html(html_code, height=1380)

# Add custom CSS to enhance the UI
st.markdown("""
    <style>
    .stSelectbox {
        width: 100%;
    }
    .stButton button {
        background-color: #FF5722;
        color: white;
        font-weight: bold;
        border-radius: 5px;
    }
    .stButton button:hover {
        background-color: #8B0000;
    }
    </style>
""", unsafe_allow_html=True)

# Footer
st.sidebar.text("Made by: \n Tyrell Fernandes\n Keegan Desouza\n Mark D'souza\n Sherwyn Misquitta\n Shaun Fernandes\n")
