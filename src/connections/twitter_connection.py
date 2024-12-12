import json
import os
from dotenv import set_key, load_dotenv
from requests_oauthlib import OAuth1Session
from src.connections.base_connection import BaseConnection
from src.helpers import print_h_bar
import tweepy

class TwitterConnection(BaseConnection):
    def __init__(self):
        super().__init__()
        self._oauth_session = None
        self.actions = {
            "get-latest-tweets": {
                "func": self.get_latest_tweets,
                "args": {"username": "str", "count": "int"}
            },
            "post-tweet": {
                "func": self.post_tweet,
                "args": {"message": "str"},
            },
            "read-timeline": {
                "func": self.read_timeline,
                "args": {"count": "int"},
            },
            "like-tweet": {
                "func": self.like_tweet,
                "args": {"tweet_id": "str"},
            }
        }

    def perform_action(self, action_name: str, **kwargs):
        """Implementation of abstract method from BaseConnection"""
        if action_name in self.actions:
            return self.actions[action_name]["func"](**kwargs)
        raise Exception(f"Unknown action: {action_name}")

    def _get_oauth(self) -> OAuth1Session:
        """Get or create OAuth session using stored credentials"""
        if self._oauth_session is None:
            load_dotenv()
            consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
            consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
            access_token = os.getenv("TWITTER_ACCESS_TOKEN")
            access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

            if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
                raise ValueError("Missing required Twitter credentials in environment")

            self._oauth_session = OAuth1Session(
                consumer_key,
                client_secret=consumer_secret,
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )

        return self._oauth_session

    def get_latest_tweets(self, username: str, count: int = 10, **kwargs):
        """
        Get latest tweets for a user
        
        Args:
            username (str): Twitter username to fetch tweets from
            count (int): Number of tweets to retrieve (default: 10)
            
        Returns:
            list: List of tweet objects containing tweet data
            
        Raises:
            Exception: If API request fails or credentials are invalid
        """
        try:
            user_id = self.get_user_id_from_username(username)
        except Exception as e:
            raise Exception(f"Failed to get user ID for username {username}: {str(e)}")

        params = {
            "tweet.fields": "created_at,public_metrics,text",
            "max_results": min(count, 100),  # API limit is 100
            "exclude": "retweets,replies"
        }

        response = self._get_oauth().get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            params=params
        )

        if response.status_code != 200:
            raise Exception(
                f"Request returned an error: {response.status_code} {response.text}"
            )

        json_response = response.json()
        return json_response.get("data", [])

    def post_tweet(self, message: str, **kwargs):
        """
        Post a new tweet
        
        Args:
            message (str): The tweet content to post
            
        Returns:
            dict: Response from Twitter API containing tweet data
            
        Raises:
            Exception: If API request fails or credentials are invalid
            ValueError: If message exceeds Twitter's character limit
        """
        if len(message) > 280:
            raise ValueError("Tweet exceeds 280 character limit")

        response = self._get_oauth().post(
            "https://api.twitter.com/2/tweets",
            json={"text": message}
        )

        if response.status_code != 201:
            raise Exception(
                f"Request returned an error: {response.status_code} {response.text}"
            )

        return response.json()

    def get_user_id_from_username(self, username: str) -> str:
        """
        Get the numeric user ID for a given Twitter username using the Twitter API v2
        """
        params = {"usernames": username}
        response = self._get_oauth().get(
            "https://api.twitter.com/2/users/by",
            params=params
        )

        if response.status_code != 200:
            raise Exception(
                f"Request returned an error: {response.status_code} {response.text}"
            )

        json_response = response.json()
        if not json_response.get("data"):
            raise Exception(f"No user found for username: {username}")
            
        return json_response["data"][0]["id"]

    def configure(self):
        """Sets up Twitter API authentication"""
        print("\n🐦 TWITTER AUTHENTICATION SETUP")

        # Check if config already exists
        if self.is_configured(verbose=False):
            print("\nTwitter API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return

        # Guide user through getting API credentials
        print("\n📝 To get your Twitter API credentials:")
        print("1. Go to https://developer.twitter.com/en/portal/dashboard")
        print("2. Create a new project and app if you haven't already")
        print("3. In your app settings, enable OAuth 1.0a with read and write permissions")
        print("4. Get your API Key (consumer key) and API Key Secret (consumer secret)")
        print_h_bar()

        # Get account details
        print("\nPlease enter your Twitter API credentials:")
        username = input("Enter your Twitter username (without @): ")
        consumer_key = input("Enter your API Key (consumer key): ")
        consumer_secret = input("Enter your API Key Secret (consumer secret): ")

        # Start OAuth process
        print("\nStarting OAuth authentication process...")

        try:
            # Get request token
            request_token_url = "https://api.twitter.com/oauth/request_token?oauth_callback=oob&x_auth_access_type=write"
            oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)

            try:
                fetch_response = oauth.fetch_request_token(request_token_url)
            except ValueError:
                print("\n❌ Error: There may be an issue with your consumer key or secret.")
                return

            resource_owner_key = fetch_response.get("oauth_token")
            resource_owner_secret = fetch_response.get("oauth_token_secret")

            # Get authorization
            base_authorization_url = "https://api.twitter.com/oauth/authorize"
            authorization_url = oauth.authorization_url(base_authorization_url)

            print("\n1. Please visit this URL to authorize the application:")
            print(authorization_url)
            print("\n2. After authorizing, Twitter will give you a PIN code.")
            verifier = input("3. Please enter the PIN code here: ")

            # Get the access token
            access_token_url = "https://api.twitter.com/oauth/access_token"
            oauth = OAuth1Session(
                consumer_key,
                client_secret=consumer_secret,
                resource_owner_key=resource_owner_key,
                resource_owner_secret=resource_owner_secret,
                verifier=verifier,
            )

            oauth_tokens = oauth.fetch_access_token(access_token_url)

            access_token = oauth_tokens.get("oauth_token")
            access_token_secret = oauth_tokens.get("oauth_token_secret")

            # Create new OAuth session with final credentials to get user ID
            self._oauth_session = OAuth1Session(
                consumer_key,
                client_secret=consumer_secret,
                resource_owner_key=access_token,
                resource_owner_secret=access_token_secret,
            )

            # Get numeric user ID using Twitter API
            try:
                user_id = self.get_user_id_from_username(username)
            except Exception as e:
                print(f"\n❌ Error getting user ID: {str(e)}")
                print("Using username as fallback...")
                user_id = username

            # Save everything to .env file
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'TWITTER_USERNAME', username)
            set_key('.env', 'TWITTER_USER_ID', user_id)
            set_key('.env', 'TWITTER_CONSUMER_KEY', consumer_key)
            set_key('.env', 'TWITTER_CONSUMER_SECRET', consumer_secret)
            set_key('.env', 'TWITTER_ACCESS_TOKEN', access_token)
            set_key('.env', 'TWITTER_ACCESS_TOKEN_SECRET', access_token_secret)

            print("\n✅ Twitter authentication successfully set up!")
            print("Your API keys, secrets, username, and user ID have been stored in the .env file.")

        except Exception as e:
            print(f"\n❌ An error occurred during setup: {str(e)}")
            return

    def is_configured(self, verbose=True) -> bool:
        """Checks if Twitter credentials are configured and valid"""
        if not os.path.exists('.env'):
            return False
            
        try:
            # Load env variables
            load_dotenv()
            consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
            consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')
            access_token = os.getenv('TWITTER_ACCESS_TOKEN')
            access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            user_id = os.getenv('TWITTER_USER_ID')

            # Check if values present
            if not all([consumer_key, consumer_secret, access_token, access_token_secret, user_id]):
                return False
            
            # Initialize tweepy client
            client = tweepy.Client(
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            
            # Try to make a minimal API call to validate credentials
            # Get the authenticated user's information
            client.get_me()
            
            # If we get here, the credentials are valid
            return True
            
        except Exception as e:
            if verbose:
                print("❌ There was an error validating your Twitter credentials:", e)
            return False

    def read_timeline(self, count=10, **kwargs) -> list:
        """Read tweets from the user's timeline"""
        user_id = os.getenv("TWITTER_USER_ID")
        if not user_id:
            raise ValueError("TWITTER_USER_ID not found in environment variables.")

        params = {
            "tweet.fields": "created_at,author_id,attachments",
            "expansions": "author_id",
            "user.fields": "name,username",
            "max_results": count
        }

        response = self._get_oauth().get(
            f"https://api.twitter.com/2/users/{user_id}/timelines/reverse_chronological",
            params=params
        )

        if response.status_code != 200:
            raise Exception(
                f"Request returned an error: {response.status_code} {response.text}"
            )

        json_response = response.json()
        tweets = json_response.get("data", [])
        user_info = json_response.get("includes", {}).get("users", [])

        # Map author_id to user information
        user_dict = {user['id']: {'name': user['name'], 'username': user['username']} for user in user_info}

        # Add user information to the tweets
        for tweet in tweets:
            author_id = tweet['author_id']
            if author_id in user_dict:
                tweet['author_name'] = user_dict[author_id]['name']
                tweet['author_username'] = user_dict[author_id]['username']
            else:
                tweet['author_name'] = "Unknown"
                tweet['author_username'] = "Unknown"

        return tweets

    def like_tweet(self, tweet_id: str, **kwargs):
        """
        Like a tweet
        
        Args:
            tweet_id (str): ID of the tweet to like
            
        Returns:
            dict: Response from Twitter API containing like data
            
        Raises:
            Exception: If API request fails or credentials are invalid
        """
        user_id = os.getenv("TWITTER_USER_ID")
        if not user_id:
            raise ValueError("TWITTER_USER_ID not found in environment variables.")

        response = self._get_oauth().post(
            f"https://api.twitter.com/2/users/{user_id}/likes",
            json={"tweet_id": tweet_id}
        )

        if response.status_code != 200:
            raise Exception(
                f"Request returned an error: {response.status_code} {response.text}"
            )

        return response.json()