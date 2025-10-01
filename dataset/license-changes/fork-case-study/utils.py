# Copyright Dawn M. Foster
# SPDX-License-Identifier: MIT

""" Utilities.
This file contains several functions that are used in multiple scripts.
"""

def set_params():
    import argparse
    import sys
    import datetime

    # Used as the default end date.
    today = datetime.date.today().strftime("%Y-%m-%d")

    # Read arguments from command line
    parser = argparse.ArgumentParser()

    parser.add_argument("-t", "--token", dest = "gh_key", help="File containing a GitHub Personal Access Token")
    parser.add_argument("-u", "--url", dest = "gh_url", help="URL for a GitHub repository")
    parser.add_argument("-b", "--begin_date", dest = "begin_date", help="Date in the format YYYY-MM-DD - gather commits after this begin date")
    parser.add_argument("-e", "--end_date", dest = "end_date", default=today, help="Date in the format YYYY-MM-DD - gather commits up until this end date. Default is today.")

    args = parser.parse_args()

    gh_url = args.gh_url
    gh_key = args.gh_key
    since_date = args.begin_date + "T00:00:00.000+00:00"
    until_date = args.end_date + "T00:00:00.000+00:00"

    url_parts = gh_url.strip('/').split('/')
    org_name = url_parts[3]
    repo_name = url_parts[4]

    # Read GitHub key from file 
    try:
        with open(gh_key, 'r') as kf:
            api_token = kf.readline().rstrip() # remove newline & trailing whitespace

    except:
        print("Error reading GH Key. This script depends on the existence of a file called gh_key containing your GitHub API token. Exiting")
        sys.exit()

    return org_name, repo_name, since_date, until_date, api_token