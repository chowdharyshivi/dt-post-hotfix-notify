import os
import re
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from http import client
import json
import re
import time
from venv import logger
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

GITHUB_PR_TITLE = os.getenv("PR_TITLE")
GITHUB_PR_URL = os.getenv("PR_URL")
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")

LINEAR_API_URL = "https://api.linear.app/graphql"
client = WebClient(token=SLACK_TOKEN)

def is_hotfix_pr(title):
    """Check if PR title indicates a hotfix."""
    if title.lower().startswith("release"):
        return False
    else:
        return True

def extract_linear_id(pr_title):
    """Extract Linear issue ID from the PR title (e.g., 'Fix bug ABC-123')"""
    match = re.search(r"[A-Z]+-\d+", pr_title)
    return match.group(0) if match else None

def get_linear_details(issueId):
    tmp_list = []
    input_json = {
        "query": """
            query issue($issueId: String!) { 
            issue(id: $issueId) {
               url
               assignee{
                    email
               }
            }
            }
                """,
        "variables": {"issueId": issueId}, 
    }
    headers = {"Accept": "application/json", "Authorization": LINEAR_API_KEY}
    api_response = requests.post(url=LINEAR_API_URL, json=input_json, headers=headers)
    print(api_response)
    tmp_list = json.loads(api_response.text)["data"]["issue"]
    extracted_info = {}
    assignee_email = tmp_list["assignee"]["email"]
    url = tmp_list['url']
    return assignee_email, url


def get_member_id(email):
    """Fetch Slack user ID by email with retry handling"""
    email_aliases = {
        "dheeraj.b@drivetrain.ai": "dheeraj.badarla@drivetrain.ai",
    }
    email = email_aliases.get(email, email)

    retries, max_retries = 0, 5
    base_wait_time = 2  # Initial wait time

    while retries < max_retries:
        try:
            response = client.users_lookupByEmail(email=email)
            return response["user"]["id"]
        except SlackApiError as e:
            error_code = e.response.get("error", "")
            if error_code == "ratelimited":
                wait_time = int(e.response.headers.get("Retry-After", base_wait_time))
                print(f"Rate limited. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                retries += 1
            elif error_code == "users_not_found":
                print(f"User with email {email} not found in Slack.")
                return None
            else:
                print(f"❌ Error fetching Slack ID: {error_code}")
                return None

    print("Max retries reached. Could not fetch Slack user ID.")
    return None

def post_message(channel_name, text):
    try:
        result = client.chat_postMessage(channel=channel_name, text=text)
    except SlackApiError as e:
        logger.error(f"Error posting message: {e}")

def send_slack_message(message_blocks):
    payload = {
        "channel": SLACK_CHANNEL,
        "blocks": message_blocks
    }
    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
        json=payload
    )
    return response.json()

def main():
    if not GITHUB_PR_TITLE:
        print("❌ Missing PR title input")
        return
    
    if is_hotfix_pr(GITHUB_PR_TITLE):
        print(f"🔍 Extracting Linear ID from PR title: {GITHUB_PR_TITLE}")
        linear_id = extract_linear_id(GITHUB_PR_TITLE)

        if not linear_id:
            print("❌ No Linear ID found in PR title.")
            return

        print(f"✅ Found Linear ID: {linear_id}")
        assignee_email,url=get_linear_details(issueId=linear_id)

        if not assignee_email:
            print("❌ Assignee email is None, assigning it to default email - shivi@drivetrain.ai")
            assignee_email = "shivi@drivetrain.ai"
        
        print(f"✅ Assignee email is {assignee_email}")
        print(f"✅ Linear url is {url}")
        slack_member_id = get_member_id(email=assignee_email)

        if not slack_member_id:
            print("❌ slack_member_id is None")
            return
        
        print(f"✅ Slack member id is {slack_member_id}")

        message_blocks = [
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<@{slack_member_id}> Quick reminder to verify your hotfix.\n\n"
                    f"PR:* <{GITHUB_PR_URL}|{GITHUB_PR_TITLE}>\n"
                    f"Please tick this message after you have verified in prod."
        }
    }
]

        print("📩 Sending Slack notification...")
        send_slack_message(message_blocks=message_blocks)
        print("✅ Slack notification sent")
    else:
        print("✅ PR is not a hotfix, skipping notification.")

if __name__ == "__main__":
    main()