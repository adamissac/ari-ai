#!/bin/sh
# Join the two final halves, mux the mix, and make the web deliverables. Run from the project root after:
#   node scripts/render.mjs --range 0,45 && node scripts/render.mjs --range 45,90
set -e
printf "file 'clip_16x9_0-45.mp4'\nfile 'clip_16x9_45-90.mp4'\n" > renders/halves.txt
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i renders/halves.txt -i audio/mix.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -shortest -movflags +faststart renders/16x9.mp4
# web: 1080p60 H.264, small enough to serve from the site
ffmpeg -hide_banner -loglevel error -y -i renders/16x9.mp4 -c:v libx264 -preset slow -crf ${CRF:-21} -profile:v high -level 4.2 \
  -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart -c:a aac -b:a 192k renders/ari-trailer-1080p.mp4
ffmpeg -hide_banner -loglevel error -y -ss 22.4 -i renders/16x9.mp4 -frames:v 1 -q:v 2 renders/ari-trailer-poster.jpg
ls -la renders/16x9.mp4 renders/ari-trailer-1080p.mp4 renders/ari-trailer-poster.jpg
ffprobe -v error -show_entries format=duration,bit_rate:stream=codec_name,width,height,r_frame_rate -of compact renders/ari-trailer-1080p.mp4
