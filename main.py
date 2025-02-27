import jwt
import time
import argparse
import requests
from typing import Dict, Any
# from openai import OpenAI


class AppStoreConnect:
    BASE_URL = "https://api.appstoreconnect.apple.com/v1"

    def __init__(self, key_id: str, issuer_id: str, private_key: str):
        self.key_id = key_id
        self.issuer_id = issuer_id
        self.private_key = private_key

    def _generate_token(self) -> str:
        payload = {
            "iss": self.issuer_id,
            "exp": int(time.time()) + 1200,
            "aud": "appstoreconnect-v1"
        }
        headers = {
            "alg": "ES256",
            "kid": self.key_id,
            "typ": "JWT"
        }
        return jwt.encode(payload, self.private_key, algorithm="ES256", headers=headers)

    def _request(self, method: str, endpoint: str, params: Dict[str, Any] = None, data: Dict[str, Any] = None) -> Any:
        headers = {
            "Authorization": f"Bearer {self._generate_token()}",
            "Content-Type": "application/json"
        }
        url = f"{self.BASE_URL}/{endpoint}"
        
        response = requests.request(method, url, headers=headers, params=params, json=data)
        response.raise_for_status()
        return response.json()

    def get_apps(self) -> Any:
        return self._request("GET", "apps")

    def get_app_description(self, app_id):
        params = {"include": "appStoreVersions"}
        endpoint = f"apps/{app_id}"

        response = self._request(endpoint, params)
        versions = response.get("included", [])

        for version in versions:
            if version["type"] == "appStoreVersions":
                version_id = version["id"]
                return self.get_app_store_info(version_id)
        return "Couldn't find description."

    def get_app_store_info(self, version_id):
        response = self._request(f"appStoreVersions/{version_id}")
        return response.get("data", {}).get("attributes", {}).get("whatsNew", "Couldn't find description.")

    def get_app_info(self, app_id: str) -> Any:
        return self._request("GET", f"apps/{app_id}")

    def get_testflight_builds(self, app_id: str) -> Any:
        return self._request("GET", f"apps/{app_id}/builds")

    def get_beta_groups(self, app_id: str) -> Any:
        return self._request("GET", f"apps/{app_id}/betaGroups")

    def create_beta_invite(self, beta_group_id: str, email: str) -> Any:
        data = {
            "data": {
                "type": "betaTesterInvitations",
                "relationships": {
                    "betaGroup": {
                        "data": {"type": "betaGroups", "id": beta_group_id}
                    },
                    "betaTester": {
                        "data": {"type": "betaTesters", "attributes": {"email": email}}
                    }
                }
            }
        }
        return self._request("POST", "betaTesterInvitations", data=data)

    def get_app_localization_info(self, app_id: str) -> Any:
        return self._request("GET", f"apps/{app_id}/appInfos?include=appInfoLocalizations")

    def get_latest_app_store_version(self, app_id: str) -> str:
        response = self._request("GET", f"apps/{app_id}/appStoreVersions")
        versions = response.get("data", [])
        if versions:
            return versions[0]["id"]
        return None

    def get_app_store_version_localizations(self, version_id: str) -> Any:
        print(f"\nFetching localizations for version {version_id}")
        response = self._request("GET", f"appStoreVersions/{version_id}/appStoreVersionLocalizations")
        print(f"Found localizations: {response}")
        return response

    def update_app_store_version_localization(self, localization_id: str,
                                            description: str = None,
                                            keywords: str = None,
                                            promotional_text: str = None,
                                            marketing_url: str = None,
                                            support_url: str = None,
                                            whats_new: str = None) -> Any:
        print(f"\nUpdating localization {localization_id}")
        data = {
            "data": {
                "type": "appStoreVersionLocalizations",
                "id": localization_id,
                "attributes": {}
            }
        }

        # Sadece non-None değerleri ekle
        if description is not None:
            data["data"]["attributes"]["description"] = description
        if keywords is not None:
            data["data"]["attributes"]["keywords"] = keywords
        if promotional_text is not None:
            data["data"]["attributes"]["promotionalText"] = promotional_text
        if marketing_url is not None:
            data["data"]["attributes"]["marketingUrl"] = marketing_url
        if support_url is not None:
            data["data"]["attributes"]["supportUrl"] = support_url
        if whats_new is not None:
            data["data"]["attributes"]["whatsNew"] = whats_new

        return self._request("PATCH", f"appStoreVersionLocalizations/{localization_id}", data=data)

    def create_app_store_version_localization(self, version_id: str, locale: str, 
                                            description: str, keywords: str = None,
                                            promotional_text: str = None,
                                            marketing_url: str = None,
                                            support_url: str = None,
                                            whats_new: str = None) -> Any:
        data = {
            "data": {
                "type": "appStoreVersionLocalizations",
                "attributes": {
                    "locale": locale,
                    "description": description
                },
                "relationships": {
                    "appStoreVersion": {
                        "data": {
                            "type": "appStoreVersions",
                            "id": version_id
                        }
                    }
                }
            }
        }

        # Opsiyonel alanları ekle
        optional_fields = {
            "keywords": keywords,
            "promotionalText": promotional_text,
            "marketingUrl": marketing_url,
            "supportUrl": support_url,
            "whatsNew": whats_new
        }

        for key, value in optional_fields.items():
            if value is not None:
                data["data"]["attributes"][key] = value

        return self._request("POST", "appStoreVersionLocalizations", data=data)

def truncate_keywords(keywords: str, max_length: int = 100) -> str:
    if not keywords:
        return ""
    
    keyword_list = [k.strip() for k in keywords.split(',')]
    
    truncated_keywords = []
    current_length = 0
    
    for keyword in keyword_list:
        new_length = current_length + len(keyword) + (2 if truncated_keywords else 0)
        
        if new_length <= max_length:
            truncated_keywords.append(keyword)
            current_length = new_length
        else:
            break
    
    return ', '.join(truncated_keywords)

def translate_content(text: str, target_language: str, is_keywords: bool = False) -> str:
    client = OpenAI()
    
    system_message = (
        "You are a professional translator. "
        f"Translate the following text to {target_language}. "
        "Maintain the tone and marketing style of the original text."
    )
    
    if is_keywords:
        system_message += " For keywords, provide a comma-separated list and keep it concise."
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": text}
        ]
    )

    translated_text = response.choices[0].message.content
    
    if is_keywords:
        translated_text = truncate_keywords(translated_text)
    
    return translated_text

if __name__ == "__main__":
    print("""
888                              888 888   
888                              888 888   
888                              888 888   
888888 888d888 88888b.  .d8888b  888 888888
888    888P"   888 "88b 88K      888 888   
888    888     888  888 "Y8888b. 888 888   
Y88b.  888     888  888      X88 888 Y88b. 
 "Y888 888     888  888  88888P' 888  "Y888
 """)
    print("Welcome to trnslt - the App Store localization tool!\n")

    parser = argparse.ArgumentParser(description="App Store localization tool")
    parser.add_argument("--api_key_id", required=True, help="API Key ID")
    parser.add_argument("--issuer_id", required=True, help="Issuer ID")
    parser.add_argument("--auth_key_path", required=True, help="Path to the private key file")

    args = parser.parse_args()

    API_KEY_ID = args.api_key_id
    ISSUER_ID = args.issuer_id
    AUTH_KEY_PATH = args.auth_key_path
    
    with open(AUTH_KEY_PATH, "r") as file:
        PRIVATE_KEY = file.read()

    target_languages = {
        "it": "Italian",
        "fi": "Finnish",
        "ja": "Japanese",
        "ko": "Korean",
        "ro": "Romanian",
        "ru": "Russian",
        "sv": "Swedish",
        "sk": "Slovak",
        "ms": "Malay",
        "no": "Norwegian",
        "pl": "Polish",
        "ar-SA": "Arabic",
        "ca": "Catalan",
        "zh-Hans": "Chinese (Simplified)",
        "zh-Hant": "Chinese (Traditional)",
        "hr": "Croatian",
        "cs": "Czech",
        "da": "Danish",
        "nl-NL": "Dutch",
        "en-AU": "English (Australia)",
        "en-CA": "English (Canada)",
        "en-GB": "English (U.K.)",
        "fr-FR": "French",
        "fr-CA": "French (Canada)",
        "de-DE": "German",
        "el": "Greek",
        "he": "Hebrew",
        "hi": "Hindi",
        "hu": "Hungarian",
        "id": "Indonesian",
        "pt-BR": "Portuguese (Brazil)",
        "pt-PT": "Portuguese (Portugal)",
        "es-MX": "Spanish (Mexico)",
        "es-ES": "Spanish (Spain)",
        "th": "Thai",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "vi": "Vietnamese"
    }

    keyword_limits = {locale: 100 for locale in target_languages.keys()}

    client = AppStoreConnect(API_KEY_ID, ISSUER_ID, PRIVATE_KEY)

    app_id = input("App ID: ")

    version_id = client.get_latest_app_store_version(app_id)
    print(f"\nLatest version ID: {version_id}")

    localizations = client.get_app_store_version_localizations(version_id)
    print(f"\nCurrent localizations: {localizations}")

    source_localization = next(
        (loc for loc in localizations.get("data", [])
         if loc["attributes"]["locale"] == "en-GB"),
        None
    )

    if source_localization:
        print(f"\nFound source localization: {source_localization}")
        source_description = source_localization["attributes"].get("description", "")
        source_keywords = source_localization["attributes"].get("keywords", "")

        existing_localizations = client.get_app_store_version_localizations(version_id)
        existing_locales = {}
        for loc in existing_localizations.get("data", []):
            locale = loc["attributes"]["locale"]
            loc_id = loc["id"]
            existing_locales[locale] = loc_id
            print(f"Found existing localization - Locale: {locale}, ID: {loc_id}")

        for locale, language in target_languages.items():
            print(f"\nProcessing {language} ({locale})...")

            try:
                translated_description = translate_content(source_description, language)
                translated_keywords = translate_content(source_keywords, language, is_keywords=True)
                
                max_length = keyword_limits.get(locale, 100)
                translated_keywords = truncate_keywords(translated_keywords, max_length)
                
                print(f"Translated keywords length: {len(translated_keywords)} characters")
                print(f"Translated keywords: {translated_keywords}")

                if locale in existing_locales:
                    print(f"Found existing localization for {locale} with ID: {existing_locales[locale]}")
                    response = client.update_app_store_version_localization(
                        localization_id=existing_locales[locale],
                        description=translated_description,
                        keywords=translated_keywords
                    )
                else:
                    print(f"Creating new localization for {locale}")
                    response = client.create_app_store_version_localization(
                        version_id=version_id,
                        locale=locale,
                        description=translated_description,
                        keywords=translated_keywords
                    )
                print(f"Successfully processed {language}")
            except Exception as e:
                error_message = str(e)
                if "The language specified is not listed for localization" in error_message:
                    print(f"Skipping {language} ({locale}) - Language not supported by App Store")
                    continue
                else:
                    print(f"Error processing localization for {language}: {error_message}")
                    print(f"Full error details: {e.__dict__}")
            
            time.sleep(1)