#!/usr/bin/env python

# Downloads counter for PixelBuilds
#
# Counts downloads for each device and sends
# them in telegram message every day

from datetime import datetime
from dotenv import load_dotenv

import asyncio
import json
import os
import requests
import telegram
import sys


async def main():
    load_dotenv("config.env")
    
    GITHUB_KEY = os.environ.get("GH_KEY")
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
    TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

    date = datetime.now()

    totalDownloads = totalPrevious = diff = 0

    skippeddevices = []
    negatives = 0

    with open("available_downloads.json", "r") as f:
        avail_downloads = json.load(f)
        
    with open("downloads.json", "r") as rf:
        real_downloads = json.load(rf)

    devices_url = "https://raw.githubusercontent.com/PixelBuildsROM/pixelbuilds_devices/main/devices.json"

    response = requests.get(devices_url).json()

    message = f"Download stats as of {date} in last 24 hours:\n"

    for device in response:
        codename = device["codename"]
        manufacturer = device["manufacturer"].lower()

        deviceDownloads = 0

        print(f"Processing {manufacturer}/{codename}...")
        
        headers = {}
        
        if GITHUB_KEY:
            headers["Authorization"] = f"Bearer {GITHUB_KEY}"
        
        if codename not in real_downloads:
            real_downloads[codename] = 0
            real_downloads[codename + "_diff"] = 0

        deviceresponse_github = requests.get(
            f"https://api.github.com/repos/PixelBuilds-Releases/{codename}/releases",
            headers=headers,
            timeout=3
        )
        deviceresponse_gitea = requests.get(
            f"https://git.pixelbuilds.org/api/v1/repos/releases/{codename}/releases",
            timeout=3
        )

        if (
            deviceresponse_github.status_code != 200
            and deviceresponse_gitea.status_code != 200
        ):
            print(
                f"Failed to get data for device {codename}!\n"
                f"Github responded: {deviceresponse_github.status_code}: {deviceresponse_github.text}"
                f"Gitea responded: {deviceresponse_gitea.status_code}: {deviceresponse_gitea.text}"
            )
            skippeddevices.append(f"{codename} - no data from both GitHub and Gitea")
            continue
        
        if (deviceresponse_github.status_code == 403):
            print("Rate limited by GitHub! Giving up to avoid disaster")
            sys.exit(1)

        if deviceresponse_github.status_code == 200:
            if len(deviceresponse_github.json()) == 0:
                print(f"No releases on GitHub for {codename}")
                skippeddevices.append(f"{codename} (GitHub) - no releases")
            else:
                print("Counting downloads from GitHub")

                for release in deviceresponse_github.json():
                    for asset in release["assets"]:
                        if not asset["name"].startswith("PixelBuilds_") and not asset[
                            "name"
                        ].endswith(".zip"):
                            continue

                        print(f"\tadding {asset['download_count']} from GitHub")
                        deviceDownloads += asset["download_count"]
        else:
            print(f"Failed to get data from GitHub for {codename}!")
            print(
                f"Response: {deviceresponse_github.status_code}: {deviceresponse_github.text}"
            )
            skippeddevices.append(f"{codename} (GitHub) - no data")

        if deviceresponse_gitea.status_code == 200:
            if len(deviceresponse_gitea.json()) == 0:
                print(f"No releases on Gitea for {codename}")
                skippeddevices.append(f"{codename} (Gitea) - no releases")
            else:
                print("Counting downloads from Gitea")

                for release in deviceresponse_gitea.json():
                    for asset in release["assets"]:
                        if not asset["name"].startswith("PixelBuilds_") and not asset[
                            "name"
                        ].endswith(".zip"):
                            continue

                        print(f"\tadding {asset['download_count']} from Gitea")
                        deviceDownloads += asset["download_count"]
        else:
            print(f"Failed to get data from Gitea for {codename}!")
            print(
                f"Response: {deviceresponse_gitea.status_code}: {deviceresponse_gitea.text}"
            )
            skippeddevices.append(f"{codename} (Gitea) - no data")

        print(f"{deviceDownloads} downloads in total for {codename}")

        try:
            avail_downloads[codename]
        except KeyError:
            avail_downloads[codename] = 0

        previous = avail_downloads[codename]

        avail_downloads[codename] = deviceDownloads

        totalDownloads += avail_downloads[codename]
        totalPrevious += previous

        diff = avail_downloads[codename] - previous
        avail_downloads[codename + "_diff"] = diff
        
        if diff < 0:
            negatives += abs(diff) 
        
        message += f"\n{codename}: {real_downloads[codename]}"
        
        if diff > 0 :
            real_downloads[codename] += diff
            real_downloads[codename + "_diff"] = diff
            message += f" (+{diff})"
            print("")

    totalDiff = totalDownloads - totalPrevious
    
    # Construct a message
    message += "\n"
    message += "\n"
    if len(skippeddevices) > 0:
        message += "Skipped devices:"

        for codename in skippeddevices:
            message += f"\n{codename}"

        message += "\n"
        message += "\n"
        
    # Write real downloads json
    if totalDiff > 0:
        if negatives > 0:
            real_downloads["_total"] += totalDiff + negatives
            real_downloads["_total_diff"] = totalDiff + negatives
        else:
            real_downloads["_total"] += totalDiff
            real_downloads["_total_diff"] = totalDiff
        real_downloads["_date"] = date
        message += f"Total: {real_downloads['_total']}"
        message += f" (+{real_downloads['_total_diff']})"
        with open("downloads.json", "w") as rf:
            rf.write(json.dumps(real_downloads, indent=2, sort_keys=True, default=str))
        print(message)
    # Write available downloads json
    avail_downloads["_date"] = date
    avail_downloads["_total"] = totalDownloads
    avail_downloads["_total_diff"] = totalDiff
    with open("available_downloads.json", "w") as f:
        f.write(json.dumps(avail_downloads, indent=2, sort_keys=True, default=str))

    # Send telegram message with results
    if TG_BOT_TOKEN and TG_CHAT_ID and totalDiff > 0:
        bot = telegram.Bot(TG_BOT_TOKEN)
        async with bot:
            await bot.send_message(text=message, chat_id=TG_CHAT_ID)

if __name__ == "__main__":
    asyncio.run(main())
