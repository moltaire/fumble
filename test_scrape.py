"""
Test scrape → assess → store with a real job URL.
"""

from pathlib import Path
from sift.assess import assess_fit
from sift.scrape import scrape_job_page
from sift.store import init_db, load_assessments, save_assessment, url_exists

PROFILE = Path("resources/profile.md").read_text()
CRITERIA = Path("resources/search-criteria.md").read_text()

URL = "https://click.stepstone.de/f/a/P3WM2xoJ0SXg2SrqzOrelQ~~/AAAmIhA~/FS__JwRE9nhZUHSxL0O_pWPguMWItBQxosWzSIT6ZH1ANKPz1hscTt6nU4Okvqon658OupicJeQ-QK1PMghSBYnj8J4rQV2tAEvjjUrEY23nQV6wM_RDGfFOPbmHgQHoHfktzOU9BXvFtAsYcKiyJT5RDVgVkvHCdaQj0YKYDSysJ-uCM7llPRrK1K5gs0YBiA9ThVWwkeaNT4fPGPjhKBE65lcRWesjbGvHCJOzoT1ih7L95PB83X0XtTAc_M4QqlVLqaiG3qiNHu9DzgFkmgWcN9KhB5GxWhH4AekTVycSg_2OQtRgm2hIA__ny7T5Ucwv8uHGsx1Olat3oRUcLsJX8K8V-kuaSx4DEln8F_fr56yZRmIKr3o-hwnyFOGkpkb6IXBrsicndjL8Yd9457dGFwXVspaBNd2r-Prv--jzVZeQr1pNnTlGvlAK20nLpKVEok1dS6KbIeEJt8zU4_7naXqxQ3A9DXOeFz2ewTgLJgSLgjlfD8vm4JcOtvITtOXXuijCAvYRLcwV90hogS7JvlXztRtCDunjy-zSSkt_ihQL3UXkUgYa4kaLFrlPecqObBpmVEONh276gYwkBTkuKORlfwuJlPSkkQwE-eYv5rySAbaIycemmB4vtrpxtdEYyGBvpkZmsrfSWPzA6ZpkZf0EuDjJwZ9uqSAYt43NUP5CRqDUoDAUjFDoL7x3qeRuivd5ox1lQJndLoJ5m05Uf_UgAnnUr812J14DctT2ge3HQ_eAXhrBwmg4MGd2CKcibGTmoVDL7D3SWKHql1cYR-rulSGEwGdAqU2TH8uEPEdoDkL8qdLtzyuXw0q1thC5xULI8NfR4LAt2Vys17PMA0dNJyMmx9oKKmKtLDsZ-bH_c8Q6r0xMKUKAZX-50OG8S_nvaQXpW4bBObT28wIFG7ZIfUZhy3BNAmBRKMxel6QyK04CA8gR76De-RtXZUH-U1A5wE2j63fIB44Gi5jcTkv3V1O50Y9TE6pAubXVthDaEgmf62ucn4bXtm8ktS3hB9TbBQVrliRie5DaqchhLCBwGMldeqFGl1FwGMYzNoReEu7-ONvmkMy9bE5lxtHX1CGHtiVc0e3gKhVXFZl8VL1tTnCNxBAu9GOtnlKrx3q326VOsJ1_KSH5zDO-ea1KW1EDw2upJrLP6e6WvztX7qREAZSd26rTKA19qbb5mxrqV3abNoaToZ8TGjsNS4D3Sp0LeGVUM_tiWCxHtSJTjV4fp4VCcIoJO5Mwt39F98Fqc2bUgvZBCIS4Zh_u20Dh8J9skLyWPvoqug-e0z_XiiY4_Adge2LvpQSJuD4fM_yVl0qjiu0LmLL5TDfWp_ND2awwR-Iq9EtsyHpQg2nDw8GgJbrLZ0njd-33xqsdlct1npUOOqs40C9pR6UE_qIwaFI_VNIuR_O6yUxDIEmVr9Zj0ITkswFFjEi6PRQzxEpFnmHyiUY-tm4jG5SZVwT1ZYptGiGD4uzp8CjeGoN4mshYIURMT9cf36aZtH4o1qKYv2yin7osy_5hZESAGZKNlrb-sRaindVZ5HRxOir77UjmvOooU4dgjL84rzovkFON6ep7tEgOJJ3cWb4MEeFfTIE7-9YSlzxjriokDVdZ7VylEehtwEYvsf9yqDjHjL5VGMa5qMzInSCgnrmNNuWdEK5jw4gqjf9jguNE54sBgGRdJ1r-xthcDJQWbWJ6Un0-wVLtUFe0ipZgNfiP"

if __name__ == "__main__":
    init_db()

    if url_exists(URL):
        print("Already assessed — skipping.")
    else:
        print("Scraping ...")
        job_text, resolved_url = scrape_job_page(URL)
        print(f"Got {len(job_text)} characters of text")
        print(f"Resolved URL: {resolved_url}\n")

        print("Assessing ...")
        result = assess_fit(
            job_text=job_text,
            profile_text=PROFILE,
            criteria_text=CRITERIA,
            url=resolved_url,
            source="stepstone",
        )

        print(f"domain_fit:  {result.domain_fit}")
        print(f"role_fit:    {result.role_fit}")
        print(f"gap_risk:    {result.gap_risk}")
        print(f"language:    {result.language}")
        print(f"suggestion:  {result.suggestion}")
        print(f"\nreasoning:\n  {result.reasoning}")

        save_assessment(result)
        print("\nSaved.")

    print("\n--- DB contents ---")
    for r in load_assessments():
        print(f"  [{r.suggestion}] {r.url[:60]}...")
