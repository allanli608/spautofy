# spautofy
automate everything music related with python

so, im really new to coding and really wanted to use spotify api for my first side project. here's what this program CURRENTLY accomplishes and what i hope it WILL accomplish in the near future:
1. take all my liked songs and sort them by genre / mood into indiviudal playlists (so that you don't have to create your own offline playlists for the airplane)
2. recommend me cool music using artificial intelligence
3. make me ai generated cover art for my playlists
4. autoplay playlists or change explicit mode based on my phone's location (i.e. autoplaying some hype gym music when i'm at the gym)
5. BLACKLIST SOME SONGS FROM EVER REACHING MY EARS BECAUSE I REALLY DON'T WANT TO LISTEN TO THEM AND IDK WHY SPOTIFY DOESN'T MAKE THIS A FEATURE YET...
6. combine and integrate all of these features into a nice front end website :)

October 6, 2023
- made my first working prototype! as of right now it sorts music into genres based on least squares of audio features located in spotify api, but it's REALLY INACCURATE. spotify's only built in "determine-genre" function is to return the genre of the artist who produced the song, but that's pretty disrespectful to artists that produce mulitple genres... gonna try to cross reference with deezer api
