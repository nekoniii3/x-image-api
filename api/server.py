# import json
import re
import asyncio
import os
import json
import random
import time
from datetime import datetime
from flask import Flask, request, abort, jsonify
from flask_cors import CORS
from twikit.guest import GuestClient

from flask import session
from datetime import timedelta
import urllib.request
import shutil
import vercel_blob

# 定数
MAX_COUNT = 20
INIT_DATA_PATH = "data/init_data.json"
TMP_FOLDER = "tmp"

app = Flask(__name__)
app.secret_key = 'abcdefghijklmn'
app.permanent_session_lifetime = timedelta(minutes=30)
# CORS(app)
CORS(app, supports_credentials=True)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Custom-Header')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    # response.headers['Access-Control-Max-Age'] = '86400'
    return response

@app.route("/", methods=['GET'])
async def return_media():

    # 返戻用変数設定
    return_data = dict(user_profile=dict(name="", description="", image=""), media_count=0, media_data=None)

    user_name = request.args.get("username")
    page_num = int(request.args.get("pagenum"))

    if user_name is None or page_num is None:
        return abort(400)
    
    # 初期データの場合
    if user_name == "" and page_num == 0:

        session.clear()
        
        initdata = read_initdata()
        session['user_name'] = initdata["user_name"]
        # session['page_num'] = 1
        session['media_data'] = initdata["media_data"]

        return jsonify(initdata)

    client = GuestClient()
    await client.activate()

    try:
        user = await client.get_user_by_screen_name(user_name)
    except Exception as e:
        print(e)
        return jsonify(return_data)

    # ユーザ情報設定
    return_data["user_profile"] = dict(name=user.name, description=user.description, image=user.profile_image_url.replace("_normal", "_400x400"))
    
    # エラーのためダミー
    # return_data["user_profile"] = dict(name="えなこ", description="名古屋出身のコスプレイヤーです(o・v・o)♪ 田村ゆかりさんとFPSゲームが好き", image="https://pbs.twimg.com/profile_images/1566064687976189953/AHpvbx_v_400x400.jpg")
    # user_id = "3061182559"

    # if user_name != session['user_name'] or page_num > 1:
    if True:

        try:
            user_tweets = await client.get_user_tweets(user.id)
            # user_tweets = await client.get_user_tweets(user_id)
            # session['user_tweets'] = user_tweets

        except Exception as e:
            # データを取得できないユーザは-1にする
            return_data["media_count"] = -1
            return jsonify(return_data)
    
        # ポストが無ければデータなしで終了
        if user_tweets is None:
            return jsonify(return_data)
    # else:
    #     user_tweets = session['user_tweets']
    
    # メディア情報セット
    media_data = set_media_data(user_tweets, page_num)
    media_count = len(user_tweets)
    
    return_data["media_count"] = media_count
    return_data["media_data"] = media_data

    # 初期データ作成用
    # with open("./data/init_data.json", mode="wt", encoding="utf-8") as f:
    #     json.dump(return_data, f, ensure_ascii=False, indent=2)

    # print(return_data)
    return jsonify(return_data)

@app.route("/", methods=['POST'])
def download_zip():

    # time.sleep(3)
    # file_url = "https://95hheycrn2ule9wh.public.blob.vercel-storage.com/test.zip"
    # return jsonify(dict(file_url = file_url))

    file_url = ""

    # if 'media_data' not in session:
    #     return jsonify(dict(file_url = file_url))
    
    # folder_name = session['user_name'] + "_" + str(random.randrange(1000000))

    # folder_path = TMP_FOLDER + "/" + folder_name

    # os.makedirs(folder_path, exist_ok=True)

    # media_data = session['media_data']
    
    # for media in media_data:

    #     if media["video_url"] != "":
    #         url = media["video_url"]
    #     else:
    #         url = media["image_url"]

    #     urllib.request.urlretrieve(url, folder_path + "/" + url[url.rfind('/') + 1:])

    # shutil.make_archive(folder_path, format='zip', root_dir=folder_path)

    folder_path = "enako_cos_1"

    file_url = put_vercel_blob(folder_path + ".zip")

    return_data = dict(file_url = file_url)

    return jsonify(return_data)

def put_vercel_blob(file):

    with open(file, 'rb') as f:
        resp = vercel_blob.put(os.path.basename(file), f.read(), {
                    "addRandomSuffix": "false",
                })
        
    print(resp["url"])

    return resp["url"]

def read_initdata():
    
    with open(INIT_DATA_PATH) as f:
        init_data = json.load(f)

    return init_data

def set_media_data(user_tweets, page_num):

    media_data = []

    start_num = (page_num - 1) * 20 + 1

    for i,tweet in enumerate(user_tweets):

        if tweet.media is None:
            continue

        if i < start_num:
            continue

        image_url, video_url = get_media_url(tweet.media[0])

        postedat = datetime.strptime(tweet.created_at,'%a %b %d %H:%M:%S %z %Y')

        postedat_str = postedat.strftime('%Y-%m-%dT%H:%M:%SZ')

        text = tweet.text

        # テキストからURL削除
        text = text[:text.find("https://t.co")]

        text = text.replace("\n", " ")[:30]
        
        if video_url != "":
            media_type="video"
            file_name = video_url[video_url.rfind('/') + 1:]
        else:
            media_type="image"
            file_name = image_url[image_url.rfind('/') + 1:]

        data = {"postid": tweet.id, "postedat" : postedat_str, "likes" :tweet.favorite_count, "media_type" : media_type, "image_url" : image_url, "video_url" : video_url, "caption" : text, "file_name" : file_name}

        media_data.append(data)

        if len(media_data) >= MAX_COUNT:
            break

    return media_data

def get_media_url(media):

    pt = r"(.*)\?.*"

    image_url = media.get("media_url_https")
    video_url = ""

    # videoがある場合の処理
    if media.get("video_info"):

        video_url = media["video_info"]["variants"][-1]["url"]
        result = re.search(pt, video_url)

        if result:
            video_url = result.group(1)   # ?tag=～を削除

    return image_url, video_url


if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', port=7860)