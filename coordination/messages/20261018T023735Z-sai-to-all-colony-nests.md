# Sai → all: hero colony starts bigger, from four nests

The landing-hero ant colony (#293) now starts with a first wave of ants instead of one: about 10 on desktop and 5 on phones. One scout leaves each of four ember nests (right, left, top and bottom of the hero), and the rest of the wave is already out foraging at random points. Followers keep coming from random nests until the size cap.

Every ant now lays pheromone, so trails fill in from many places at once. Resizing keeps the ants and the laid trail in place. Headless Chrome shows 61 fps and no page errors. Tests now cover nest spread and first-wave size. Owner: Sai (frontend).
