#require mozreviewdocker
  $ . $TESTDIR/hgext/reviewboard/tests/helpers.sh
  $ . $TESTDIR/pylib/mozreviewbots/tests/helpers.sh
  $ commonenv rb-test-eslintbot

Running setup
  $ eslintsetup

Enter into the test repo director
  $ cd client

Create a non-JS file
  $ echo foo0 > foo

Create mach
  $ cat >> mach << EOF
  > #!/usr/bin/env python
  > import sys
  > import subprocess
  > subprocess.call(["eslint"] + sys.argv[1:])
  > EOF

Create .eslintrc
  $ touch .eslintrc

Commit the files
  $ hg commit -A -m 'root commit' > /dev/null
  $ hg phase --public -r .
  $ hg push --noreview > /dev/null

Create a review request that doesn't touch any Javascript files

  $ bugzilla create-bug TestProduct TestComponent bug1
  $ echo irrelevant > foo
  $ hg commit -m 'Bug 1 - No Javascript changes'
  $ hg push --config reviewboard.autopublish=false > /dev/null
  (review requests lack reviewers; visit review url to assign reviewers)
  $ rbmanage publish 1

  $ python -m eslintbot --config-path ../eslintbot.ini
  INFO:mozreviewbot:reviewing revision: 27ed10e6e90a (review request: 2)
  INFO:mozreviewbot:not reviewing revision: 27ed10e6e90a514ad461a5a7147a9134de0ca799 no relevant Javascript changes in commit

  $ rbmanage dumpreview 2
  id: 2
  status: pending
  public: true
  bugs:
  - '1'
  commit: null
  submitter: default+5
  summary: Bug 1 - No Javascript changes
  description:
  - Bug 1 - No Javascript changes
  - ''
  - 'MozReview-Commit-ID: 124Bxg'
  target_people: []
  extra_data:
    calculated_trophies: true
  commit_extra_data:
    p2rb: true
    p2rb.author: test
    p2rb.commit_id: 27ed10e6e90a514ad461a5a7147a9134de0ca799
    p2rb.first_public_ancestor: dc42edca6edd9dd5a8346b1a881281263d3a10ad
    p2rb.identifier: bz://1/mynick
    p2rb.is_squashed: false
  diffs:
  - id: 2
    revision: 1
    base_commit_id: dc42edca6edd9dd5a8346b1a881281263d3a10ad
    name: diff
    extra: {}
    patch:
    - diff --git a/foo b/foo
    - '--- a/foo'
    - +++ b/foo
    - '@@ -1,1 +1,1 @@'
    - -foo0
    - +irrelevant
    - ''
  approved: false
  approval_failure: A suitable reviewer has not given a "Ship It!"

Cleanup

  $ mozreview stop
  stopped 9 containers
