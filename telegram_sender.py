import requests
import sys


def get_message_url(token, chatid, message):
    return f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chatid}&text={message}"


if __name__ == "__main__":
    with open("keyfile.txt", "r", encoding="utf-8") as f:
        token, chatid = f.read().splitlines()
    if sys.argv[1] not in ["START", "ETA", "FINISHED"]:
        raise NotImplementedError("Not implemented what you're trying")
    if sys.argv[1] == "FINISHED":
        message = "Experiment finished"
        url = get_message_url(token, chatid, message)
    if sys.argv[1] == "START":
        message = "Experiment successfully started"
        url = get_message_url(token, chatid, message)
    requests.get(url).json()
