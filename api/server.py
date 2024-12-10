import re
import os
import json
import random
from datetime import datetime
from datetime import timedelta
from flask import Flask, request, abort, jsonify
from flask_cors import CORS
from twikit.guest import GuestClient
import urllib.request
import shutil
import vercel_blob
# from flask import session

# 定数
MAX_COUNT = 20
INIT_DATA_PATH = "data/init_data.json"
TMP_FOLDER = "/tmp"

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SC_KEY"]
app.permanent_session_lifetime = timedelta(minutes=30)
CORS(app, supports_credentials=True)

@app.after_request
def after_request(response):
    # response.headers.add("Access-Control-Allow-Origin", "http://localhost:3000")
    response.headers.add("Access-Control-Allow-Origin", "https://x-image-gallery-git-dev-nekoniii3s-projects.vercel.app")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Custom-Header")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    # response.headers["Access-Control-Max-Age"] = "86400"
    return response

@app.route("/", methods=["GET"])
async def return_media():

    # 返戻用変数設定
    return_data = dict(user_profile=dict(name="", description="", image="", banner=""), media_count=0, media_data=None)

    user_name = request.args.get("username")
    page_num = int(request.args.get("pagenum"))

    if user_name is None or page_num is None:
        return abort(400)
    
    # 初期データの場合
    if user_name == "" and page_num == 0:

        initdata = read_initdata()
        return jsonify(initdata)

    client = GuestClient()
    await client.activate()

    try:
        user = await client.get_user_by_screen_name(user_name)
    except Exception as e:
        print(e)
        return jsonify(return_data)

    # ユーザ情報設定
    return_data["user_profile"] = dict(name=user.name, description=user.description, \
                                       image=user.profile_image_url.replace("_normal", "_400x400"), \
                                        buner=user.profile_banner_url)
    
    try:
        user_tweets = await client.get_user_tweets(user.id)

    except Exception as e:
        # データを取得できないユーザは-1にする
        return_data["media_count"] = -1
        return jsonify(return_data)
    
    # ポストが無ければデータなしで終了
    if user_tweets is None:
        return jsonify(return_data)
    
    # メディア情報セット
    media_data, endflg = set_media_data(user_tweets, page_num)
    media_count = len(user_tweets)
    
    return_data["media_count"] = media_count
    return_data["endflg"] = endflg
    return_data["media_data"] = media_data

    # 初期データ作成用
    # with open("./data/flg_test.json", mode="wt", encoding="utf-8") as f:
    #     json.dump(return_data, f, ensure_ascii=False, indent=2)

    return jsonify(return_data)

@app.route("/", methods=["POST"])
def download_zip():

    file_url = ""

    # Bodyデータ取得
    data = json.loads(request.data.decode("utf-8"))

    file_list = data["filelist"]
    folder_name = data["username"] + "_" + str(random.randint(10000000, 99999999))

    folder_path = TMP_FOLDER + "/" + folder_name
    os.makedirs(folder_path, exist_ok=True)

    # urllibを利用するため偽装
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent","Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36")]
    urllib.request.install_opener(opener)

    for file in file_list:

        if file[2] != "":
            url = file[2]   # ViedeoURL
        else:
            url = file[1]   # ImageURL

        print(url)
        print(folder_path + "/" + url[url.rfind("/") + 1:])
        urllib.request.urlretrieve(url, folder_path + "/" + url[url.rfind("/") + 1:])

    shutil.make_archive(folder_path, format="zip", root_dir=folder_path)

    file_url = put_vercel_blob(folder_path + ".zip")

    return_data = dict(file_url = file_url)

    return jsonify(return_data)

def put_vercel_blob(file):

    with open(file, "rb") as f:
        resp = vercel_blob.put(os.path.basename(file), f.read(), {
                    "addRandomSuffix": "false",
                })
        
    return resp["url"]

def read_initdata():
    
    with open(INIT_DATA_PATH) as f:
        init_data = json.load(f)

    return init_data

def set_media_data(user_tweets, page_num):

    media_data = []

    start_num = (page_num - 1) * 20 + 1

    media_num = 0
    end_flg = True

    for i,tweet in enumerate(user_tweets):

        if tweet.media is None:
            continue

        media_num += 1

        if media_num < start_num:
            continue

        image_url, video_url = get_media_url(tweet.media[0])

        postedat = datetime.strptime(tweet.created_at,"%a %b %d %H:%M:%S %z %Y")

        postedat_str = postedat.strftime("%Y-%m-%dT%H:%M:%SZ")

        text = tweet.text

        # テキストからURL削除
        text = text[:text.find("https://t.co")]

        text = text.replace("\n", " ")[:30]
        
        if video_url != "":
            media_type="video"
            file_name = video_url[video_url.rfind("/") + 1:]
        else:
            media_type="image"
            file_name = image_url[image_url.rfind("/") + 1:]

        data = {"postid": tweet.id, "postedat" : postedat_str, "likes" :tweet.favorite_count, "media_type" : media_type, "image_url" : image_url, "video_url" : video_url, "caption" : text, "file_name" : file_name}

        media_data.append(data)

        if len(media_data) >= MAX_COUNT:
            # データが最大件数に達した場合
            end_flg = False
            break

        print(end_flg)

    return media_data, end_flg

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
    # app.debug = True
    app.run(host="0.0.0.0", port=7860)