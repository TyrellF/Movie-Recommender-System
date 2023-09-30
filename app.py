import streamlit as st
import streamlit.components.v1 as components
import pickle
import pandas as pd
import requests

# Set page title and icon
st.set_page_config(
    page_title="Movie Recommender",
    page_icon="🎬",
    layout="wide",
)

import zlib

movies_dict = pickle.load(open('movie_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
with open('similarity_compressed.pkl', 'rb') as compressed_file:
    similarity = pickle.loads(zlib.decompress(compressed_file.read()))

# similarity = pickle.load(open('similarity.pkl', 'rb'))

# Sample API to fetch movie details
API_KEY = "df957ac8237d3d811c021c6112a49de2"

def fetch_movie_details(movie_id):
    response = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US")
    data = response.json()
    return data

def fetch_movie_credits(movie_id):
    response = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={API_KEY}")
    data = response.json()
    return data

def fetch_movie_videos(movie_id):
    response = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={API_KEY}")
    data = response.json()
    return data
def fetch_trending_movies():
    response = requests.get(f"https://api.themoviedb.org/3/trending/movie/day?api_key={API_KEY}")
    data = response.json()
    return data.get('results', [])

def fetch_poster(movie_id):
    response = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US")
    data = response.json()
    return "https://image.tmdb.org/t/p/w300/" + data['poster_path']  # Adjust the width here


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
        release_date = fetch_movie_details(movie_id)['release_date']
        rating = fetch_movie_details(movie_id)['vote_average']

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
selected_movie_name = st.sidebar.selectbox(
    'Choose A Movie🎬:',
    movies['title'].values
)
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
        movie_details = fetch_movie_details(movies[movies['title'] == selected_movie_name]['movie_id'].values[0])
        credits = fetch_movie_credits(movies[movies['title'] == selected_movie_name]['movie_id'].values[0])
        videos = fetch_movie_videos(movies[movies['title'] == selected_movie_name]['movie_id'].values[0])

        poster_url = fetch_poster(movie_details['id'])
        st.subheader(f"Details for {selected_movie_name}")
        st.image(poster_url, width=200)

        st.write(f"**Release Date:** {movie_details['release_date']}")
        st.write(f"**Overview:** {movie_details['overview']}")
        st.write(f"**Rating:** {movie_details['vote_average']}")
        st.write(f"**Runtime:** {movie_details['runtime']} minutes")

        # Display director(s)
        directors = [crew['name'] for crew in credits['crew'] if crew['job'] == 'Director']
        st.write(f"**Director(s):** {', '.join(directors)}")

        # Display cast members
        cast = [cast_member['name'] for cast_member in credits['cast'][:10]]  # Display the top 10 cast members
        st.write(f"**Cast:** {', '.join(cast)}")

        # Display movie trailers
        trailers = [video['name'] for video in videos['results'] if video['site'] == 'YouTube']
        if trailers:
            st.write("**Trailers:**")
            for trailer_name in trailers:
                trailer_key = next(video['key'] for video in videos['results'] if video['name'] == trailer_name)
                st.write(f"[{trailer_name}](https://www.youtube.com/watch?v={trailer_key})")


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

    for movie in trending_movies:
        poster_url = fetch_poster(movie['id'])
        st.image(poster_url, caption=movie['title'], width=200)
        st.write(f"**Release Date:** {movie['release_date']}")
        st.write(f"**Overview:** {movie['overview']}")
        st.write(f"**Rating:** {movie['vote_average']}")

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
