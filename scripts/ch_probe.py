import base64, json, os, urllib.request, urllib.error
KEY = os.environ["CH_KEY"]
AUTH = "Basic " + base64.b64encode((KEY + ":").encode()).decode()
def get(path):
    req = urllib.request.Request("https://api.company-information.service.gov.uk" + path, headers={"Authorization": AUTH})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200]
for n in ["00876597", "03063806"]:
    s, d = get(f"/company/{n}")
    print("company", n, s, {k: d.get(k) for k in ("company_status", "company_status_detail", "date_of_creation", "date_of_cessation", "sic_codes")} if s == 200 else d)
for q in [
    "/advanced-search/companies?sic_codes=25400&incorporated_from=2024-01-01&incorporated_to=2024-12-31&size=1",
    "/advanced-search/companies?sic_codes=25400,30400,84220&incorporated_from=2024-01-01&incorporated_to=2024-12-31&size=1",
    "/advanced-search/companies?sic_codes=25400&sic_codes=30400&incorporated_from=2024-01-01&incorporated_to=2024-12-31&size=1",
    "/advanced-search/companies?sic_codes=25400&company_status=dissolved&dissolved_from=2024-01-01&dissolved_to=2024-12-31&size=1",
    "/advanced-search/companies?sic_codes=25400&dissolved_from=2024-01-01&dissolved_to=2024-12-31&size=1",
    "/advanced-search/companies?sic_codes=25400&dissolved_from=2008-01-01&dissolved_to=2008-12-31&size=1",
    "/advanced-search/companies?sic_codes=25400&company_status=active&size=1",
]:
    s, d = get(q)
    if s == 200:
        print(q, s, "hits", d.get("hits"), "keys", sorted(d.keys()), "item", {k: d["items"][0].get(k) for k in ("company_status", "date_of_creation", "date_of_cessation", "sic_codes")} if d.get("items") else None)
    else:
        print(q, s, d)
