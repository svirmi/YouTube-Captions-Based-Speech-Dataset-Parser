#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess

import os
import io
import re

import shutil

import wave
import csv

import time

from utils import audio_utils
from utils import yt_subs_utils
from utils.yt_utils import download_yt_audio

from utils.stats_util import write_stats
from utils.slicing_utils import is_bad_piece, is_bad_subs, slice_audio_by_silence

from utils import csv_utils
from utils.stats_util import write_stats

import sys
import const



def process_video(yt_video_id):   

    print 'Processing video '+yt_video_id

    total_speech_length_sec = 0
    total_pieces_count = 0
    good_pieces_count = 0

    autosubs = yt_subs_utils.get_subs(yt_video_id, auto_subs=True)

    timed_words = yt_subs_utils.get_timed_words(yt_video_id)
    
    # download audio
    audio_original_path = download_yt_audio(yt_video_id)

    video_dir_path = os.path.join(const.VIDEO_DATA_DIR, yt_video_id);
    if not os.path.exists(video_dir_path):
        os.makedirs(video_dir_path)

    # convert to wav
    audio_wav_path = os.path.join(const.VIDEO_DATA_DIR, yt_video_id+"/audio.wav")

    if not os.path.exists(audio_wav_path):
        audio_utils.convert_to_wav(audio_original_path, audio_wav_path)

    # load wave object
    wave_obj = wave.open(audio_wav_path, "r")

    # slice by VAD silence
    sliced_pieces, avg_len_sec = slice_audio_by_silence(wave_obj, vad_silence_volume_param=0)
    total_pieces_count = len(sliced_pieces)

    print("sliced into %i pieces with average length of %f seconds" % (total_pieces_count, avg_len_sec))


    parts_folder_path = os.path.join(video_dir_path, "parts/");
    if not os.path.exists(parts_folder_path):
        os.makedirs(parts_folder_path)

    csv_rows = []

    for i, piece in enumerate(sliced_pieces):
        START_PREC_SEC = 0.5
        END_PREC_SEC = 0.2

        # for each piece find words that are inside it
        words = [w for w in timed_words if float(w["start"])/1000 >= piece["start"]-START_PREC_SEC and float(w["end"])/1000 <= piece["end"]+END_PREC_SEC]

        if len(words) == 0:
            continue

        words = sorted(words, key=lambda w: w["start"])

        if abs(piece["start"] - float(words[0]["start"])/1000) > 0.5 or abs(piece["end"] - float(words[-1]["end"])/1000) > 0.5:
            #print("skip not precise bounds %i" % i)
            continue

        words_str = " ".join([w["word"] for w in words])
        words_str = words_str.encode("utf-8")

        # print("%s-%s %s" % (
        #     str(datetime.timedelta(seconds=piece["start"])),
        #     str(datetime.timedelta(seconds=piece["end"])),
        #     words_str
        #                     )
        # )

        if is_bad_subs(words_str):
            #print("skip bad subs %i: %s" % (i, words_str))
            continue

        part_wav_path = os.path.join(parts_folder_path, "%s_%i.wav" % (yt_video_id, i))
        audio_utils.save_wave_samples_to_file(piece["samples"], 1, 2, 16000, part_wav_path)
        wav_filesize = os.path.getsize(part_wav_path)


        SAMPLE_RATE = 16000
        BYTE_WIDTH = 2
        audio_length = float(wav_filesize)/SAMPLE_RATE/BYTE_WIDTH
        total_speech_length_sec += audio_length

        if is_bad_piece(audio_length, words_str):
            #print("skip is_bad_piece %i" % i)
            # remove file
            os.remove(part_wav_path)
            continue

        audio_per_symbol_density = audio_length/len(words_str)
        if  audio_per_symbol_density > 0.07:
            print("skip too high audio per symbol density: %f" % (audio_per_symbol_density))
            continue
        
        good_pieces_count += 1

        csv_rows.append([part_wav_path, wav_filesize, words_str])


    print("added %i pieces" % len(csv_rows))

    csv_path = os.path.join(video_dir_path, "parts.csv")

    csv_utils.write_rows_to_csv(csv_path, csv_rows)

    # stats
    write_stats(video_dir_path, ["speech_duration", "subs_quality", "good_samples", "total_samples"], [
                total_speech_length_sec, 1, good_pieces_count, total_pieces_count])

if __name__ == "__main__":
    yt_video_id = "1mWhDsN_yN4"
    process_video(yt_video_id)
