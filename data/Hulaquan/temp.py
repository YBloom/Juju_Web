import requests
import re
import os
import json

def get_recommendation(limit=12, page=0, timeMark=True, tags=None):
    # get events from recommendation API
    recommendation_url = "https://clubz.cloudsation.com/site/getevent.html?filter=recommendation&access_token="
    try:
        recommendation_url = recommendation_url + "&limit" + str(limit) + "&page=" + str(page)
        response = requests.get(recommendation_url)
        print(recommendation_url)
        response.raise_for_status()
        json_data = response.content.decode('utf-8-sig')
        json_data = json.loads(json_data)
        result = []
        for event in json_data["events"]:
            print(limit, page, event["basic_info"]["title"])
            if not timeMark or (timeMark and event["timeMark"] > 0):
                if not tags or (tags and any(tag in event["tags"] for tag in tags)):
                    result.append(event["basic_info"])
    except requests.RequestException as e:
        return f"Error fetching recommendation: {e}"
    
    return json_data["count"], result

get_recommendation(73, 0)