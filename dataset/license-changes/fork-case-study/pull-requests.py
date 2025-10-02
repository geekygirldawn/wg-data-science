# Copyright Dawn M. Foster
# SPDX-License-Identifier: MIT

""" This gathers data from pull requests for a specified repo.
Because of limitations in the GitHub GraphQL API, this data is
collected starting with the most recent PRs, so there is no
end date required, only a beginning date. It will collect data
about all PRs from the beginning date to today. The PRs after the 
desired end date will be filtered out in a later step.

Use --help to see the inputs required.

Note: there is a lot of error handling built into this script
along with collection of data about failure points, since for 
collection of very large repos, you might want to manually 
restart a collection at the point where it failed. This was 
done when GitHub was having a bunch of time out issues, which
happens periodically, but not often. It will only stop if it hits
an error on the same group of commits more than 3 times. Otherwise, 
it prints a message, but continues collecting, including getting
the group that failed.

Output (files are stored in the data-files directory)
* GitHub API response code (should be "<Response [200]>") printed to the screen
* startCursor (before_cursor variable) printed to the screen to show collection status
* PR data pickle file containing json data
"""

# Function with the GitHub GraphQL API call.
def make_pr_query(before_cursor = None):
    return """
query repo_prs($org_name: String!, $repo_name: String!){
    repository(owner: $org_name, name: $repo_name) {
        pullRequests(last: 25, before: BEFORE) {
        pageInfo {
            hasPreviousPage
            startCursor
            hasNextPage
            endCursor
        }  
        nodes {
            url
            author{
            login
            }
            commits(first: 100){
            totalCount
            nodes{
                commit{
                id
                oid
                }
            }
            }
            id
            number
            createdAt
            state
            closedAt
                    mergedAt
            mergedBy{
                login
            }
            mergeCommit{
                oid
                authors{
                totalCount
                }
            }
            reviews(first: 10){
                nodes{
                createdAt
                state
                body
                author{
                    login
                }
                }
            }
            comments(first: 10){
                nodes{
                createdAt
                body
                author{
                    login
                }
                }
            }
            }
        }
    }
}
    """.replace(
        "BEFORE", '"{}"'.format(before_cursor) if before_cursor else "null"
            )

def collect_prs(org_name, repo_name, since_date, until_date, api_token):
    import requests
    import json
    import time
    import pickle
    import sys
    import pandas as pd

    beg_dt = pd.to_datetime(since_date, utc=True)

    output_file = 'data-files/pr-data/' + org_name + '-' + repo_name + '-prs-' + since_date[0:10] + '-' + until_date[0:10] + '.pkl'

    url = 'https://api.github.com/graphql'
    headers = {'Authorization': 'token %s' % api_token}

    results_prs = []

    has_next_page = True
    before_cursor = None
    failed_cursor = None
    fail_increment = 1

    while has_next_page:

        print(before_cursor)

        # The try should catch weird, unexpected, unanticipated errors
        try:

            query = make_pr_query(before_cursor)
            variables = {"before_cursor": before_cursor, "org_name": org_name, "repo_name": repo_name}

            r = requests.post(url=url, json={'query': query, 'variables': variables}, headers=headers)
            print(r)

            json_data = json.loads(r.text)
            
            results_prs.append(json_data)

            has_next_page = json_data['data']['repository']['pullRequests']['pageInfo']['hasPreviousPage']

            before_cursor = json_data['data']['repository']['pullRequests']['pageInfo']['startCursor']

            # End data gathering if we've reached the beginning date
            for pr in json_data['data']['repository']['pullRequests']['nodes']:
                if pd.to_datetime(pr['createdAt'], utc=True) < beg_dt:
                    has_next_page = False
        
        except:
            # Note: this after cursor is most likely the one before the failure, not the one failing
            # Printing it to allow debugging or to start collection again where it failed.
            print("Unexpected Error: before_cursor = ", before_cursor, "failure number", fail_increment)

            # This happens when the last loop also failed.
            if failed_cursor == before_cursor:
                if fail_increment > 3:
                    output_results = output_file + str(before_cursor) + "fail"
                    print("Error occurred 3 times in a row. Saving results list to:")
                    print(output_results)
                    with open(output_results, 'wb') as f:
                        pickle.dump(results_prs, f)
                    print("Exiting ...")
                    sys.exit
                fail_increment+=1
            # These are new failures, so reset failed_cursor and increment
            else:
                failed_cursor = before_cursor
                fail_increment = 1
                print("Sleeping 60 sec")
                time.sleep(60)

    print("Saving PRs to", output_file)
    with open(output_file, 'wb') as f:
        pickle.dump(results_prs, f)
    
    return(results_prs)

def add_bot(peopleDict, login):
    peopleDict[login] = {
        'name': login,
        'company': 'Bot',
        'email': [],
        'type': 'Bot',
        'numPRs': 0
        }
    return(peopleDict)

def add_user(login, peopleDict, g, bot_list):
    if login in bot_list:
        peopleDict = add_bot(peopleDict, login)
    
    try: 
        peopleDict[login]
    except:
        GHauthor = g.get_user(login)
        peopleDict[login] = {
            'company': GHauthor.company,
            'name': GHauthor.name,
            'type': GHauthor.type,
            'numPRs': 0,
            'mergedPRs': 0
        }
        if GHauthor.email != None:
            peopleDict[login]['email'] = [GHauthor.email]
        else: 
            peopleDict[login]['email'] = []
    
    return(peopleDict)

def create_peopleDict(results_prs, api_token):
    from github import Github
    import pandas as pd

    print("Building peopleDict")
    peopleDict = {}

    g = Github(api_token)
    print("Starting rate limit info:", g.get_rate_limit())

    data = pd.read_csv('data-files/pr-data/known-bots.csv', header=None)
    bot_list = data[0].tolist()

    for item in results_prs:
        prs = item['data']['repository']['pullRequests']['nodes']
        
        for pr in prs:

            if pr['createdAt'] > since_date:
                try:
                    peopleDict = add_user(pr['author']['login'], peopleDict, g, bot_list)

                    for comments in pr['comments']['nodes']:
                        peopleDict = add_user(comments['author']['login'], peopleDict, g, bot_list)

                    for reviews in pr['reviews']['nodes']:
                        peopleDict = add_user(reviews['author']['login'], peopleDict, g, bot_list)
                except:
                    # This can occur for deleted accounts, some types of bot accounts, and other reasons
                    print("Failed to add someone to people dict from PR", pr['url'])

    
    return(peopleDict)

# Setting up basic parameters for the information needed to run the script
from utils import set_params
org_name, repo_name, since_date, until_date, api_token = set_params()

results_prs = collect_prs(org_name, repo_name, since_date, until_date, api_token)

peopleDict = create_peopleDict(results_prs, api_token)

# Writing peopleDict to a file
import pickle
people_output_file = 'data-files/pr-data/' + org_name + '-' + repo_name + '-people-' + since_date[0:10] + '-' + until_date[0:10] + '.pkl'
print("Saving peopleDict to", people_output_file)
with open(people_output_file, 'wb') as f:
    pickle.dump(peopleDict, f)




