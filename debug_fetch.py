from scrapers.naukri import NaukriScraper

s = NaukriScraper()
html = s.fetch("https://www.naukri.com/data-analyst-jobs-in-bangalore")

with open("naukri_debug.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Saved, length:", len(html))
s.close()