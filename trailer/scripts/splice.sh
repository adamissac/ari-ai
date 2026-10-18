#!/bin/sh
# Swap re-rendered ranges into the master (exact frames, 60 fps) and re-encode the web MP4 with the current mix.
# Ranges re-rendered with: node scripts/render.mjs --range 13,16 | 44,52 | 75,83
set -e
F=60
ffmpeg -hide_banner -loglevel error -y -i renders/16x9.mp4 -i renders/clip_16x9_13-16.mp4 -i renders/clip_16x9_44-52.mp4 -i renders/clip_16x9_75-83.mp4 -i audio/mix.wav \
  -filter_complex "[0:v]split=4[s0][s1][s2][s3];\
[s0]trim=start_frame=0:end_frame=$((13*F)),setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];\
[s1]trim=start_frame=$((16*F)):end_frame=$((44*F)),setpts=PTS-STARTPTS[c];[2:v]setpts=PTS-STARTPTS[d];\
[s2]trim=start_frame=$((52*F)):end_frame=$((75*F)),setpts=PTS-STARTPTS[e];[3:v]setpts=PTS-STARTPTS[f];\
[s3]trim=start_frame=$((83*F)):end_frame=$((90*F)),setpts=PTS-STARTPTS[g];\
[a][b][c][d][e][f][g]concat=n=7:v=1:a=0[v]" \
  -map "[v]" -map 4:a -c:v libx264 -preset slow -crf ${CRF:-21} -profile:v high -level 4.2 -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 -c:a aac -b:a 192k -shortest -movflags +faststart renders/ari-trailer-1080p.mp4
ffmpeg -hide_banner -loglevel error -y -ss 22.4 -i renders/ari-trailer-1080p.mp4 -frames:v 1 -q:v 2 renders/ari-trailer-poster.jpg
ffprobe -v error -count_packets -show_entries format=duration,size:stream=codec_name,nb_read_packets,r_frame_rate -of compact renders/ari-trailer-1080p.mp4
