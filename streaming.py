from __future__ import absolute_import, print_function

from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream

# Go to http://apps.twitter.com and create an app.
# The consumer key and secret will be generated for you after
consumer_key="ngyEI20AOXmNDuKA0s1J5Gt2l"
consumer_secret="LzzPeoF5EipYsMwnO5uC1u7pKVrHDatERb9CBTjDJX1dZKcRX7"

# After the step above, you will be redirected to your app's page.
# Create an access token under the the "Your access token" section
access_token="15629921-O5zGhOvfB6w20xjmcDZMcudwzLVG5qn7ckjPqH97Y"
access_token_secret="HdndTCcaPt1bDunZXDwDexMmpbOBkrlGa2zr5hgTXJjyL"

class StdOutListener(StreamListener):
    """ A listener handles tweets are the received from the stream.
    This is a basic listener that just prints received tweets to stdout.

    """
    def on_data(self, data):
        print(data)
        return True

    def on_error(self, status):
        print(status)

if __name__ == '__main__':
    l = StdOutListener()
    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    stream = Stream(auth, l)
    stream.filter(track=['basketball'])