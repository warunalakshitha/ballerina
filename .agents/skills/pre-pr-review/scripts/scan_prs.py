"""List open PRs needing review: no summary yet (NEW) or head != reviewed sha (MOVED).
Skips drafts, approved PRs and don't-merge/dnm/hold/wip labels. Fetch failures are ERR, never NEW."""
import json, re, subprocess, sys, time
REPO = 'ballerina-nutcracker/ballerina'
ME = __import__('os').environ.get('REVIEWER', 'warunalakshitha')
def gh(*a, tries=4):
    for i in range(tries):
        r = subprocess.run(['gh', *a], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        time.sleep(3 * (i + 1))
    raise RuntimeError(r.stderr.strip()[:200])
prs = json.loads(gh('pr', 'list', '--repo', REPO, '--state', 'open', '--limit', '200',
                    '--json', 'number,headRefOid,isDraft,reviewDecision,labels,mergeable'))
for p in prs:
    if p['isDraft'] or p['reviewDecision'] == 'APPROVED' or any(re.search('merge|dnm|hold|wip', l['name'], re.I) for l in p['labels']):
        continue
    n, sha = p['number'], p['headRefOid']
    try:
        out = gh('api', f'repos/{REPO}/issues/{n}/comments?per_page=100', '--paginate', '--jq',
                 '.[] | select(.user.login=="' + ME + '") | select(.body|test("PR review summary")) | .body | @json')
        bodies = [json.loads(l) for l in out.splitlines() if l.strip()]
    except RuntimeError as e:
        print(n, 'ERR', sha[:9], p['mergeable'], e); continue
    shas = re.findall(r'reviewed `([0-9a-f]{7,40})', bodies[-1]) if bodies else []
    if not shas:
        print(n, 'NEW', sha[:9], p['mergeable'])
    elif not sha.startswith(shas[-1]):
        print(n, 'MOVED', shas[-1], '->', sha[:9], p['mergeable'])
