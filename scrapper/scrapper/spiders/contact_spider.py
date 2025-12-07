import scrapy
import re
import json
import phonenumbers
from scrapy.linkextractors import LinkExtractor


ROLE_KEYWORDS = [
    # Inglés
    "CEO", "CTO", "CFO", "COO",
    "Founder", "Co-Founder",
    "Manager", "Director", "Marketing Manager",
    "Project Manager", "Sales Manager",
    "Lead Developer", "Software Engineer",
    "Developer", "Engineer", "Administrator",
    "Consultant", "Customer Support",
    # Español
    "Director General", "Gerente", "Fundador",
    "Cofundador", "Responsable", "Responsable Comercial",
    "Jefe de Ventas", "Jefe de Marketing",
    "Atención al Cliente", "Administrador"
]


class ContactSpider(scrapy.Spider):
    name = "contact"

    def __init__(self, urls="", spider_mode=False, max_pages=None, fields="", *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.start_urls = [u.strip() for u in urls.split(",") if u.strip()]
        self.spider_mode = str(spider_mode).lower() == "true"
        self.max_pages = int(max_pages) if max_pages not in ("", None, "None") else None

        # If fields empty -> extract ALL fields
        if fields.strip() == "":
            self.fields = ["email", "phone", "name", "role"]
        else:
            self.fields = [f.strip().lower() for f in fields.split(",") if f.strip()]

        self.visited = set()
        self.pages_scraped = 0
        self.link_extractor = LinkExtractor()

    # Detectar país a partir del TLD
    def detect_region(self, url: str) -> str:
        domain = url.split("/")[2]
        if domain.endswith(".fr"): return "FR"
        if domain.endswith(".it"): return "IT"
        if domain.endswith(".de"): return "DE"
        if domain.endswith(".co.uk") or domain.endswith(".uk"): return "GB"
        if domain.endswith(".pt"): return "PT"
        if domain.endswith(".us"): return "US"
        return "ES"

    # Extraer NOMBRE
    def extract_nearby_name(self, html: str, start: int, end: int):
        if "name" not in self.fields:
            return None
        window = 200
        snippet = html[max(0, start - window): min(len(html), end + window)]
        regex = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
        matches = re.findall(regex, snippet)
        return max(matches, key=len) if matches else None

    # Extraer ROL
    def extract_nearby_role(self, html: str, start: int, end: int):
        if "role" not in self.fields:
            return None
        window = 200
        snippet = html[max(0, start - window): min(len(html), end + window)]
        regex = r"\b(" + "|".join(re.escape(r) for r in ROLE_KEYWORDS) + r")\b"
        matches = re.findall(regex, snippet, flags=re.I)
        return matches[0] if matches else None

    # Peticiones iniciales
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=url, callback=self.parse)

    # PARSE PRINCIPAL
    def parse(self, response):

        if self.max_pages and self.pages_scraped >= self.max_pages:
            return

        if response.url in self.visited:
            return
        self.visited.add(response.url)
        self.pages_scraped += 1

        html = response.text
        region = self.detect_region(response.url)

        contacts = []

        # -----------------------------------------------------------
        # EMAILS
        # -----------------------------------------------------------
        if "email" in self.fields or "name" in self.fields or "role" in self.fields:
            email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
            for match in re.finditer(email_regex, html):
                email = match.group(0)
                start, end = match.start(), match.end()

                name = self.extract_nearby_name(html, start, end)
                role = self.extract_nearby_role(html, start, end)

                contacts.append({
                    "email": email if "email" in self.fields else None,
                    "phone": None,
                    "name": name,
                    "role": role
                })

        # -----------------------------------------------------------
        # EMAILS OFUSCADOS
        # -----------------------------------------------------------
        if "email" in self.fields:
            obf_regex = (
                r"([a-zA-Z0-9_.+-]+)\s*(?:\(|\[)?at(?:\)|\])?\s*"
                r"([a-zA-Z0-9_.+-]+)\s*(?:\(|\[)?dot(?:\)|\])?\s*"
                r"([a-zA-Z]{2,})"
            )
            for user, domain, tld in re.findall(obf_regex, html, re.I):
                email = f"{user}@{domain}.{tld}"
                idx = html.lower().find(user.lower())

                if idx != -1:
                    name = self.extract_nearby_name(html, idx, idx + len(user))
                    role = self.extract_nearby_role(html, idx, idx + len(user))
                else:
                    name = None
                    role = None

                contacts.append({
                    "email": email,
                    "phone": None,
                    "name": name,
                    "role": role
                })

        # -----------------------------------------------------------
        # TELÉFONOS
        # -----------------------------------------------------------
        if "phone" in self.fields or "name" in self.fields or "role" in self.fields:
            phone_regex = r"""
                (?:(?:\+|00)\d{1,3})?
                [\s\-.()]?
                (?:\d{2,4}[\s\-.()]?){2,4}
            """
            raw_phones = re.findall(phone_regex, html, re.VERBOSE)

            valid_phones = set()
            for raw in raw_phones:
                try:
                    num = phonenumbers.parse(raw, region)
                    if phonenumbers.is_valid_number(num):
                        valid_phones.add(
                            phonenumbers.format_number(
                                num,
                                phonenumbers.PhoneNumberFormat.E164
                            )
                        )
                except:
                    pass

            for phone in valid_phones:
                last_digits = phone[-6:]
                m = re.search(last_digits, html)

                if m:
                    name = self.extract_nearby_name(html, m.start(), m.end())
                    role = self.extract_nearby_role(html, m.start(), m.end())
                else:
                    name = None
                    role = None

                contacts.append({
                    "email": None,
                    "phone": phone if "phone" in self.fields else None,
                    "name": name,
                    "role": role
                })

        # -----------------------------------------------------------
        # OUTPUT
        # -----------------------------------------------------------
        item = {
            "url": response.url,
            "contacts": contacts
        }

        print(json.dumps(item, ensure_ascii=False))
        yield item

        # -----------------------------------------------------------
        # MODO ARAÑA
        # -----------------------------------------------------------
        if self.spider_mode:
            for link in self.link_extractor.extract_links(response):
                if link.url not in self.visited:
                    yield scrapy.Request(link.url, callback=self.parse)
