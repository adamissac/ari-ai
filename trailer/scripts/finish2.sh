#!/bin/sh
# 3:48 explainer: join the two final halves, mux the mix, make the web MP4 + poster. Run from the project root after:
#   node scripts/render.mjs --range 0,114 && node scripts/render.mjs --range 114,228
set -e
printf "file 'clip_16x9_0-114.mp4'\nfile 'clip_16x9_114-228.mp4'\n" > renders/halves2.txt
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i renders/halves2.txt -i audio/mix.wav \
  -map 0:v -map 1:a -c:v libx264 -preset slow -crf ${CRF:-20} -profile:v high -level 4.2 -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -c:a aac -b:a 192k -shortest -movflags +faststart renders/ari-explainer-1080p.mp4
ffmpeg -hide_banner -loglevel error -y -ss 16.5 -i renders/ari-explainer-1080p.mp4 -frames:v 1 -q:v 2 renders/ari-explainer-poster.jpg
ffprobe -v error -count_packets -show_entries format=duration,size:stream=codec_name,nb_read_packets,r_frame_rate -of compact renders/ari-explainer-1080p.mp4
