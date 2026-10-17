# Sai → all: Defense Lab page polish

- Removed the teal "THE DEFENSE STORY" box above the replay, because it repeated the page intro and the map's own attacker/defender bar.
- The play bar and timeline now sit directly under the network map, so the controls stay next to what they control. Outcome and ground-truth controls moved into a footer strip of the replay card.
- Sections now have eyebrows ("01 · Watch", "02 · Compare"), a larger lede, numbered intro steps, and a quieter simulation caveat (still `lab-caveat`, same text).
- The scoreboard legend class is renamed `.lab-defenders` because `.lab-legend` collided with the map legend.
- Test ids and copy are unchanged; no data or backend changes. Owner: Sai (frontend).
