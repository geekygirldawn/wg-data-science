# Copyright Dawn M. Foster
# SPDX-License-Identifier: MIT

"""Gets Commit Data Used with PR data 
This gathers commit data and matches it to PRs. The author data
is used to augment what can be found in the PR data. For example,
email address data is often better when looking at PRs, rather 
than GitHub profiles that are associated with a PR.

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
* endCursor (after_cursor variable) printed to the screen to show collection status
* Commit data pickle file containing json data
"""

# Function with the GitHub GraphQL API call.
def get_commits_query(after_cursor = None):
    return """
query repo_commits($org_name: String!, $repo_name: String!, $since_date: GitTimestamp!, $until_date: GitTimestamp!){
  repository(owner: $org_name, name: $repo_name) {
  ... on Repository{
      defaultBranchRef{
          target{
              ... on Commit{
                  history(since: $since_date, until: $until_date, first:25 after: AFTER){
                  pageInfo {
                   hasNextPage
                   endCursor
                 }    
                  edges{
                          node{
                              ... on Commit{
                                committedDate
                                deletions
                                additions
                                oid
                                associatedPullRequests(first: 100){
                                  nodes{
                                    id
                                    number
                                    mergeCommit{
                                      oid
                                    }
                                    }
                                    }
                                authors(first:100) {
                                  nodes {
                                    date
                                    email
                                    user {
                                      login
                                      company
                                      email
                                      name
                                      }
                                    }
                                  }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
  }
}
    """.replace(
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
            )

import requests
import json
import time
import pickle
import sys
from utils import set_params

# Setting up basic parameters for the information needed to run the script
org_name, repo_name, since_date, until_date, api_token = set_params()

output_file = 'data-files/pr-data/' + org_name + '-' + repo_name + '-commits-' + since_date[0:10] + '-' + until_date[0:10] + '.pkl'

url = 'https://api.github.com/graphql'
headers = {'Authorization': 'token %s' % api_token}

results = []

has_next_page = True
after_cursor = None
failed_cursor = None
fail_increment = 1

while has_next_page:

    print(after_cursor)

    # The try should catch weird, unexpected, unanticipated errors
    try:
        query = get_commits_query(after_cursor)

        variables = {"org_name": org_name, "repo_name": repo_name, "since_date": since_date, "until_date": until_date}

        r = requests.post(url=url, json={'query': query, 'variables': variables}, headers=headers)
        print(r)

        if r.status_code == 200:

            json_data = json.loads(r.text)

            results.append(json_data)

            has_next_page = json_data['data']['repository']['defaultBranchRef']['target']['history']['pageInfo']['hasNextPage']

            after_cursor = json_data['data']['repository']['defaultBranchRef']['target']['history']['pageInfo']['endCursor']

        else:
            print("Sleeping 5 sec")
            time.sleep(5)
    except:
        # Note: this after cursor is most likely the one before the failure, not the one failing
        # Printing it to allow debugging or to start collection again where it failed.
        print("Unexpected Error: after_cursor = ", after_cursor, "failure number", fail_increment)

        # This happens when the last loop also failed.
        if failed_cursor == after_cursor:
            if fail_increment > 3:
                output_results = output_file + str(after_cursor) + "fail"
                print("Error occurred 3 times in a row. Saving results list to:")
                print(output_results)
                with open(output_results, 'wb') as f:
                    pickle.dump(results, f)
                print("Exiting ...")
                sys.exit
            fail_increment+=1
        # These are new failures, so reset failed_cursor and increment
        else:
            failed_cursor = after_cursor
            fail_increment = 1
            print("Sleeping 60 sec")
            time.sleep(60)

print("Saving commits to", output_file)
with open(output_file, 'wb') as f:
    pickle.dump(results, f)