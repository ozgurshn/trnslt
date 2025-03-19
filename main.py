import jwt
import time
import argparse
import requests
from typing import Dict, Any
from openai import OpenAI
import os
import sys

os.environ["OPENAI_API_KEY"] = ""

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

    def truncate_app_info_text(self, text, max_length=30):
        if not text or len(text) <= max_length:
            return text
        
        if " - " in text:
            parts = text.split(" - ", 1)
            if len(parts[0]) <= max_length - 3:
                return parts[0] + " -"
            else:
                return parts[0][:max_length]
        elif " " in text and text.find(" ") < max_length - 3:
            last_space = text.rfind(" ", 0, max_length - 3)
            if last_space > 0:
                return text[:last_space] + "..."
        
        return text[:max_length-3] + "..."

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

    def update_app_info_localization(self, localization_id: str, name: str = None, subtitle: str = None) -> Any:
        print(f"\nUpdating app info localization {localization_id}")
        print(f"Original Name: {name}")
        print(f"Original Subtitle: {subtitle}")
        
        if name is not None:
            original_name = name
            name = self.truncate_app_info_text(name)
            if name != original_name:
                print(f"Name truncated to: {name} (to fit 30 character limit)")
        
        if subtitle is not None:
            original_subtitle = subtitle
            subtitle = self.truncate_app_info_text(subtitle)
            if subtitle != original_subtitle:
                print(f"Subtitle truncated to: {subtitle} (to fit 30 character limit)")
        
        data = {
            "data": {
                "type": "appInfoLocalizations",
                "id": localization_id,
                "attributes": {
                    "name": name if name is not None else "",
                    "subtitle": subtitle if subtitle is not None else ""
                }
            }
        }

        try:
            response = self._request("PATCH", f"appInfoLocalizations/{localization_id}", data=data)
            print(f"Successfully updated app info localization with name: {name}")
            print(f"Successfully updated app info localization with subtitle: {subtitle}")
            return response
        except requests.exceptions.HTTPError as e:
            print(f"Error updating app info localization: {str(e)}")
            print(f"Request data: {data}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            raise

    def create_app_info_localization(self, app_info_id: str, locale: str, name: str = None, subtitle: str = None) -> Any:
        print(f"\nCreating app info localization for {locale}")
        print(f"Original Name: {name}")
        print(f"Original Subtitle: {subtitle}")
        
        if name is not None:
            original_name = name
            name = self.truncate_app_info_text(name)
            if name != original_name:
                print(f"Name truncated to: {name} (to fit 30 character limit)")
        
        if subtitle is not None:
            original_subtitle = subtitle
            subtitle = self.truncate_app_info_text(subtitle)
            if subtitle != original_subtitle:
                print(f"Subtitle truncated to: {subtitle} (to fit 30 character limit)")
        
        try:
            existing_localizations = self._request("GET", f"appInfos/{app_info_id}/appInfoLocalizations")
            for loc in existing_localizations.get("data", []):
                if loc["attributes"]["locale"] == locale:
                    return self.update_app_info_localization(
                        localization_id=loc["id"],
                        name=name,
                        subtitle=subtitle
                    )
            
            translated_name = name
            translated_subtitle = subtitle
            
            try:
                create_data = {
                    "data": {
                        "type": "appInfoLocalizations",
                        "attributes": {
                            "locale": locale,
                            "name": translated_name,
                            "subtitle": translated_subtitle
                        },
                        "relationships": {
                            "appInfo": {
                                "data": {
                                    "type": "appInfos",
                                    "id": app_info_id
                                }
                            }
                        }
                    }
                }
                
                try:
                    create_response = self._request("POST", "appInfoLocalizations", data=create_data)
                    print(f"Create response: {create_response}")
                    print(f"Successfully created app info localization with name: {translated_name}")
                    print(f"Successfully created app info localization with subtitle: {translated_subtitle}")
                    return create_response
                except requests.exceptions.HTTPError as e:
                    if hasattr(e, 'response') and e.response.status_code == 409:
                        print("Conflict detected. Checking if we should use the other app info...")
                        
                        other_app_info_id = None
                        for app_info in existing_localizations.get("data", []):
                            if app_info["id"] != app_info_id and app_info["attributes"].get("state") == "PREPARE_FOR_SUBMISSION":
                                other_app_info_id = app_info["id"]
                                print(f"Found alternative app_info_id: {other_app_info_id}")
                                break
                        
                        if other_app_info_id:
                            print(f"Trying with the alternative app info ID: {other_app_info_id}")
                            create_data["data"]["relationships"]["appInfo"]["data"]["id"] = other_app_info_id
                            try:
                                create_response = self._request("POST", "appInfoLocalizations", data=create_data)
                                print(f"Create response with alternative app info: {create_response}")
                                print(f"Successfully created app info localization with name: {translated_name}")
                                print(f"Successfully created app info localization with subtitle: {translated_subtitle}")
                                return create_response
                            except Exception as alt_e:
                                print(f"Error with alternative app info: {str(alt_e)}")
                                raise e
                        else:
                            print("No alternative app info found. Checking for existing localization...")
                            try:
                                retry_response = self._request("GET", f"appInfos/{app_info_id}/appInfoLocalizations")
                                existing_loc_id = None
                                
                                for loc in retry_response.get("data", []):
                                    if loc["attributes"]["locale"] == locale:
                                        existing_loc_id = loc["id"]
                                        break
                                
                                if existing_loc_id:
                                    update_response = self.update_app_info_localization(
                                        localization_id=existing_loc_id,
                                        name=translated_name,
                                        subtitle=translated_subtitle
                                    )
                                    print(f"Update response after retry: {update_response}")
                                    return update_response
                                else:
                                    print(f"Could not create or update localization for {locale}")
                                    return None
                            except Exception as retry_e:
                                print(f"Error during retry: {str(retry_e)}")
                                return None
                    else:
                        print(f"Non-409 error: {str(e)}")
                        if hasattr(e, 'response'):
                            print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                            print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                        raise e
                
            except Exception as e:
                print(f"Error during app info localization creation: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                    print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                print(f"Skipping app info localization for {locale}")
                return None
            
        except requests.exceptions.HTTPError as e:
            print(f"Error creating app info localization: {str(e)}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
                
                if e.response.status_code == 409:
                    print("Conflict detected, trying to update existing localization...")
                    try:
                        all_locs = self._request("GET", f"appInfos/{app_info_id}/appInfoLocalizations")
                        for loc in all_locs.get("data", []):
                            if loc["attributes"]["locale"] == locale:
                                return self.update_app_info_localization(
                                    localization_id=loc["id"],
                                    name=name,
                                    subtitle=subtitle
                                )
                    except Exception as inner_e:
                        print(f"Error during conflict resolution: {str(inner_e)}")
            return None

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

def get_language_from_locale(locale: str) -> str:
    """Convert a locale code to a human-readable language name."""
    locale_mapping = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "de": "German",
        "it": "Italian",
        "ja": "Japanese",
        "ko": "Korean",
        "pt": "Portuguese",
        "ru": "Russian",
        "zh": "Chinese",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "no": "Norwegian",
        "pl": "Polish",
        "tr": "Turkish",
        "ar": "Arabic",
        "he": "Hebrew",
        "th": "Thai",
        "cs": "Czech",
        "hu": "Hungarian",
        "ro": "Romanian",
        "uk": "Ukrainian",
        "vi": "Vietnamese",
        "id": "Indonesian",
        "ms": "Malay",
        "sk": "Slovak",
        "el": "Greek",
        "hr": "Croatian",
        "ca": "Catalan",
        "hi": "Hindi"
    }
    
    # Handle locales with country codes (e.g., en-US, zh-Hans)
    if "-" in locale:
        base_locale = locale.split("-")[0]
    else:
        base_locale = locale
    
    return locale_mapping.get(base_locale, "English")  # Default to English if not found

def translate_content(text: str, target_language: str, is_keywords: bool = False, model: str = "gpt-4", source_locale: str = None) -> str:
    if not text:
        return ""
        
    client = OpenAI(timeout=60.0)
    
    # Use provided source_locale or fall back to default value
    locale = source_locale or "en-US"
    source_language = get_language_from_locale(locale)
    
    # If target_language is a locale code (e.g. "fr-FR"), convert it to a language name
    if "-" in target_language or target_language in target_languages.keys():
        target_language_name = target_languages.get(target_language, get_language_from_locale(target_language))
    else:
        target_language_name = target_language
    
    system_message = (
        "You are a professional translator specializing in app store descriptions and keywords. "
        f"Translate the following text from {source_language} to {target_language_name}. "
        "Maintain the marketing style and ensure the translation is natural and appealing to "
        f"{target_language_name}-speaking users. "
    )
    
    if is_keywords:
        system_message += (
            "Provide keywords as a comma-separated list. "
            "Focus on commonly searched terms in the target language. "
            "Keep keywords concise and relevant to the app."
        )
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            timeout=60.0 
        )

        translated_text = response.choices[0].message.content.strip()
        
        if is_keywords:
            translated_text = truncate_keywords(translated_text)
        
        print(f"Original text: {text}")
        print(f"Translated text: {translated_text}")
        
        return translated_text
        
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return text 

if __name__ == "__main__":

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set!")
        sys.exit(1)

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
    parser.add_argument("--app_id", required=True, help="App Store app ID")
    parser.add_argument("--source_locale", default="en-US", 
                      help="Source locale for translations (default: en-US). Examples: en-US, en-GB, fr-FR")
    parser.add_argument("--openai_model", default="gpt-4", 
                      help="OpenAI model to use for translations (default: gpt-4). Options: gpt-4, gpt-3.5-turbo, etc.")
    parser.add_argument("--translate_app_info", action="store_true", default=True,
                      help="Translate App Information: app name and subtitle (default: True)")
    parser.add_argument("--translate_app_store", action="store_true", default=True,
                      help="Translate App Store content: description and keywords (default: True)")
    parser.add_argument("--only_app_info", action="store_true", 
                      help="If set, only App Information (name and subtitle) will be translated. This is a shortcut that sets --translate_app_store=False")
    parser.add_argument("--only_app_store", action="store_true", 
                      help="If set, only App Store content (description and keywords) will be translated. This is a shortcut that sets --translate_app_info=False")

    args = parser.parse_args()

    API_KEY_ID = args.api_key_id
    ISSUER_ID = args.issuer_id
    AUTH_KEY_PATH = args.auth_key_path
    APP_ID = args.app_id
    SOURCE_LOCALE = args.source_locale
    OPENAI_MODEL = args.openai_model
    
    # Process translation options
    TRANSLATE_APP_INFO = args.translate_app_info
    TRANSLATE_APP_STORE = args.translate_app_store
    
    # Handle special flags
    if args.only_app_info:
        TRANSLATE_APP_INFO = True
        TRANSLATE_APP_STORE = False
        print("Note: Only App Information (name and subtitle) will be translated.")
    elif args.only_app_store:
        TRANSLATE_APP_INFO = False
        TRANSLATE_APP_STORE = True
        print("Note: Only App Store content (description and keywords) will be translated.")
    
    # Validate source locale
    if SOURCE_LOCALE not in target_languages and not SOURCE_LOCALE.startswith("en-"):
        print(f"Warning: Source locale '{SOURCE_LOCALE}' is not in our known locales list.")
        print("It will still be used, but may cause issues with the App Store API.")
        print("Consider using one of the following locales:")
        print(", ".join(sorted(target_languages.keys())))
        print("\nProceeding with the provided locale anyway...")
    
    # Validate OpenAI model
    known_models = ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]
    if OPENAI_MODEL not in known_models:
        print(f"Warning: OpenAI model '{OPENAI_MODEL}' is not in our list of known models.")
        print("It will still be used, but may cause API errors if invalid.")
        print("Known models are:", ", ".join(known_models))
        print("\nProceeding with the provided model anyway...")
    
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

    print("\nLocalization process started!")
    print(f"Using source locale: {SOURCE_LOCALE}")
    print(f"Using OpenAI model: {OPENAI_MODEL}")
    print(f"Translating App Information (name & subtitle): {TRANSLATE_APP_INFO}")
    print(f"Translating App Store content (description & keywords): {TRANSLATE_APP_STORE}")
    
    version_id = client.get_latest_app_store_version(APP_ID)
    print(f"\nLatest version ID: {version_id}")

    localizations = client.get_app_store_version_localizations(version_id)
    print(f"\nCurrent localizations: {localizations}")

    source_localization = next(
        (loc for loc in localizations.get("data", [])
         if loc["attributes"]["locale"] == SOURCE_LOCALE),
        None
    )

    if source_localization:
        print(f"\nFound source localization: {source_localization}")
        source_description = source_localization["attributes"].get("description", "")
        source_keywords = source_localization["attributes"].get("keywords", "")
        source_marketing_url = source_localization["attributes"].get("marketingUrl", "")
        source_support_url = source_localization["attributes"].get("supportUrl", "")
        
        print(f"\nSource description length: {len(source_description)}")
        print(f"Source keywords: {source_keywords}")
        print(f"Source marketing URL: {source_marketing_url}")
        print(f"Source support URL: {source_support_url}")
        
        app_info_response = client.get_app_localization_info(APP_ID)
        print("\nApp Info Response:", app_info_response)
        
        app_info_id = None
        source_app_info = None
        
        if app_info_response.get("data"):
            for app_info in app_info_response["data"]:
                if app_info["attributes"].get("state") == "PREPARE_FOR_SUBMISSION":
                    app_info_id = app_info["id"]
                    print(f"Found app_info_id in PREPARE_FOR_SUBMISSION state: {app_info_id}")
                    break
            
            if not app_info_id:
                app_info_id = app_info_response["data"][0]["id"]
                print(f"Found app_info_id: {app_info_id}")
        
        if app_info_response.get("included"):
            for loc in app_info_response["included"]:
                if (loc["type"] == "appInfoLocalizations" and 
                    loc["attributes"].get("locale") == SOURCE_LOCALE):
                    source_app_info = loc
                    break
        
        if not source_app_info:
            print("Warning: Could not find source localization, fetching directly...")
            try:
                direct_response = client._request("GET", f"appInfos/{app_info_id}/appInfoLocalizations")
                for loc in direct_response.get("data", []):
                    if loc["attributes"].get("locale") == SOURCE_LOCALE:
                        source_app_info = loc
                        break
            except Exception as e:
                print(f"Error fetching direct localizations: {str(e)}")
        
        if source_app_info:
            source_name = source_app_info["attributes"].get("name", "MoneyBox - Smart Savings")
            source_subtitle = source_app_info["attributes"].get("subtitle", "Your Smart Savings Companion")
            print(f"\nSource app name: {source_name}")
            print(f"Source app subtitle: {source_subtitle}")
            
            try:
                print("Fetching all current app info localizations...")
                all_app_info_response = client._request("GET", f"appInfos/{app_info_id}")
                if "data" in all_app_info_response:
                    current_app_info = all_app_info_response["data"]
                    print(f"Current app info: {current_app_info}")
                    
                    all_localizations_response = client._request("GET", f"appInfos/{app_info_id}/appInfoLocalizations")
                    existing_app_info_localizations = {}
                    
                    if "data" in all_localizations_response:
                        for loc in all_localizations_response["data"]:
                            if loc["type"] == "appInfoLocalizations":
                                locale = loc["attributes"]["locale"]
                                existing_app_info_localizations[locale] = {
                                    "id": loc["id"],
                                    "name": loc["attributes"].get("name", ""),
                                    "subtitle": loc["attributes"].get("subtitle", "")
                                }
                                print(f"Found existing app info for {locale}: {existing_app_info_localizations[locale]}")
            except Exception as e:
                print(f"Error fetching app info details: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"Response status: {e.response.status_code}")
                    print(f"Response body: {e.response.text}")
        
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
                if app_info_id and source_name and source_subtitle and TRANSLATE_APP_INFO:
                    try:
                        print(f"=== Processing App Info for {language} ({locale}) ===")
                        print(f"Translating app name for {language}...")
                        translated_name = translate_content(source_name, language, model=OPENAI_MODEL, source_locale=SOURCE_LOCALE)
                        
                        print(f"Translating app subtitle for {language}...")
                        translated_subtitle = translate_content(source_subtitle, language, model=OPENAI_MODEL, source_locale=SOURCE_LOCALE)
                        
                        all_app_infos = client._request("GET", f"apps/{APP_ID}/appInfos")
                        primary_app_info_id = app_info_id
                        
                        submission_ready_app_info = None
                        for app_info in all_app_infos.get("data", []):
                            if app_info["attributes"].get("state") == "PREPARE_FOR_SUBMISSION":
                                submission_ready_app_info = app_info
                                break
                        
                        if submission_ready_app_info:
                            print(f"Using app info in PREPARE_FOR_SUBMISSION state: {submission_ready_app_info['id']}")
                            primary_app_info_id = submission_ready_app_info["id"]
                                                
                        existing_loc_id = None
                        existing_app_info_id = None
                        
                        app_info_ids_to_check = []
                        if primary_app_info_id:
                            app_info_ids_to_check.append(primary_app_info_id)
                        
                        for app_info in all_app_infos.get("data", []):
                            if app_info["id"] != primary_app_info_id:
                                app_info_ids_to_check.append(app_info["id"])
                        
                        for check_app_info_id in app_info_ids_to_check:
                            try:
                                loc_response = client._request("GET", f"appInfos/{check_app_info_id}/appInfoLocalizations")
                                for loc in loc_response.get("data", []):
                                    if loc["attributes"]["locale"] == locale:
                                        existing_loc_id = loc["id"]
                                        existing_app_info_id = check_app_info_id
                                        print(f"Found existing localization for {locale} in app info {check_app_info_id}: {existing_loc_id}")
                                        break
                                
                                if existing_loc_id:
                                    break
                            except Exception as e:
                                print(f"Error checking app info {check_app_info_id} for localizations: {str(e)}")
                        
                        if existing_loc_id:
                            print(f"Updating existing localization {existing_loc_id} for {locale}")
                            try:
                                update_response = client.update_app_info_localization(
                                    localization_id=existing_loc_id,
                                    name=translated_name,
                                    subtitle=translated_subtitle
                                )
                                print(f"Successfully updated app info localization for {language}")
                                print(f"Updated name: {translated_name}")
                                print(f"Updated subtitle: {translated_subtitle}")
                            except Exception as e:
                                print(f"Error updating app info localization: {str(e)}")
                                if hasattr(e, 'response'):
                                    print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                                    print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                        else:
                            print(f"Creating new app info localization for {locale} in app info {primary_app_info_id}")
                            create_data = {
                                "data": {
                                    "type": "appInfoLocalizations",
                                    "attributes": {
                                        "locale": locale,
                                        "name": translated_name,
                                        "subtitle": translated_subtitle
                                    },
                                    "relationships": {
                                        "appInfo": {
                                            "data": {
                                                "type": "appInfos",
                                                "id": primary_app_info_id
                                            }
                                        }
                                    }
                                }
                            }
                            
                            try:
                                create_response = client._request("POST", "appInfoLocalizations", data=create_data)
                                print(f"Successfully created app info localization for {language}")
                                print(f"Created with name: {translated_name}")
                                print(f"Created with subtitle: {translated_subtitle}")
                            except requests.exceptions.HTTPError as e:
                                if hasattr(e, 'response') and e.response.status_code == 409:
                                    print(f"Conflict creating app info localization for {locale}")
                            
                            
                                    for alt_app_info_id in app_info_ids_to_check:
                                        if alt_app_info_id != primary_app_info_id:
                                            print(f"Trying with alternative app info ID: {alt_app_info_id}")
                                            create_data["data"]["relationships"]["appInfo"]["data"]["id"] = alt_app_info_id
                                            try:
                                                create_response = client._request("POST", "appInfoLocalizations", data=create_data)
                                                print(f"Successfully created app info localization with alternative app info")
                                                print(f"Created with name: {translated_name}")
                                                print(f"Created with subtitle: {translated_subtitle}")
                                                break
                                            except Exception as alt_e:
                                                print(f"Error with alternative app info {alt_app_info_id}: {str(alt_e)}")
                                    try:
                                        print("Final attempt to find and update existing localization...")
                                        for check_app_info_id in app_info_ids_to_check:
                                            retry_response = client._request("GET", f"appInfos/{check_app_info_id}/appInfoLocalizations")
                                            for loc in retry_response.get("data", []):
                                                if loc["attributes"]["locale"] == locale:
                                                    retry_loc_id = loc["id"]
                                                    print(f"Found localization in final check: {retry_loc_id}")
                                                    update_response = client.update_app_info_localization(
                                                        localization_id=retry_loc_id,
                                                        name=translated_name,
                                                        subtitle=translated_subtitle
                                                    )
                                                    print(f"Successfully updated localization in final attempt")
                                                    print(f"Updated name: {translated_name}")
                                                    print(f"Updated subtitle: {translated_subtitle}")
                                                    break
                                    except Exception as final_e:
                                        print(f"Error in final attempt: {str(final_e)}")
                                else:
                                    print(f"Error creating app info localization: {str(e)}")
                                    if hasattr(e, 'response'):
                                        print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                                        print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                    except Exception as e:
                        print(f"Error processing app info localization for {language}: {str(e)}")
                        if hasattr(e, 'response'):
                            print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                            print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                
                if locale in existing_locales and TRANSLATE_APP_STORE:
                    existing_loc = next(
                        (loc for loc in existing_localizations.get("data", [])
                         if loc["attributes"]["locale"] == locale),
                        None
                    )
                    
                    existing_description = existing_loc["attributes"].get("description", "")
                    existing_keywords = existing_loc["attributes"].get("keywords", "")
                    existing_marketing_url = existing_loc["attributes"].get("marketingUrl", "")
                    existing_support_url = existing_loc["attributes"].get("supportUrl", "")
                    
                    if not existing_description.strip():
                        print(f"Description missing for {language}, translating...")
                        translated_description = translate_content(source_description, language, model=OPENAI_MODEL, source_locale=SOURCE_LOCALE)
                    else:
                        print(f"Using existing description for {language}")
                        translated_description = existing_description
                    
                    if not existing_keywords.strip():
                        print(f"Keywords missing for {language}, translating...")
                        translated_keywords = translate_content(source_keywords, language, is_keywords=True, model=OPENAI_MODEL, source_locale=SOURCE_LOCALE)
                        translated_keywords = truncate_keywords(translated_keywords, keyword_limits.get(locale, 100))
                    else:
                        print(f"Using existing keywords for {language}")
                        translated_keywords = existing_keywords
                    
                    print(f"Updating localization for {locale} with ID: {existing_locales[locale]}")
                    try:
                        response = client.update_app_store_version_localization(
                            localization_id=existing_locales[locale],
                            description=translated_description,
                            keywords=translated_keywords,
                            marketing_url=source_marketing_url if source_marketing_url else existing_marketing_url,
                            support_url=source_support_url if source_support_url else existing_support_url
                        )
                        print(f"Successfully updated localization for {language}")
                    except Exception as e:
                        print(f"Error updating localization for {language}: {str(e)}")
                        if hasattr(e, 'response'):
                            print(f"Response status: {e.response.status_code if hasattr(e.response, 'status_code') else 'unknown'}")
                            print(f"Response body: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
                elif TRANSLATE_APP_STORE:
                    print(f"Creating new localization for {locale}")
                    try:
                        translated_description = translate_content(source_description, language, model=OPENAI_MODEL, source_locale=SOURCE_LOCALE)
                        translated_keywords = translate_content(source_keywords, language, is_keywords=True, model=OPENAI_MODEL, source_locale=SOURCE_LOCALE)
                        translated_keywords = truncate_keywords(translated_keywords, keyword_limits.get(locale, 100))
                        
                        try:
                            response = client.create_app_store_version_localization(
                                version_id=version_id,
                                locale=locale,
                                description=translated_description,
                                keywords=translated_keywords,
                                marketing_url=source_marketing_url,
                                support_url=source_support_url
                            )
                            print(f"Successfully created localization for {language}")
                        except requests.exceptions.HTTPError as e:
                            if hasattr(e, 'response') and e.response.status_code == 409:
                                print(f"Conflict when creating localization for {locale}. The localization likely already exists.")
                                retry_response = client._request("GET", f"appStoreVersions/{version_id}/appStoreVersionLocalizations")
                                for loc in retry_response.get("data", []):
                                    if loc["attributes"]["locale"] == locale:
                                        loc_id = loc["id"]
                                        print(f"Found existing localization ID: {loc_id}")
                                        update_response = client.update_app_store_version_localization(
                                            localization_id=loc_id,
                                            description=translated_description,
                                            keywords=translated_keywords,
                                            marketing_url=source_marketing_url,
                                            support_url=source_support_url
                                        )
                                        print(f"Successfully updated existing localization for {language}")
                                        break
                            else:
                                print(f"Error creating localization: {str(e)}")
                                if hasattr(e, 'response'):
                                    print(f"Response status: {e.response.status_code}")
                                    print(f"Response body: {e.response.text}")
                    except KeyboardInterrupt:
                        print(f"\n\nProcess interrupted by user while processing {language}. Stopping execution.")
                        sys.exit(0)
                    except Exception as e:
                        print(f"Error translating content for {language}: {str(e)}")
                        continue
                print(f"Successfully processed {language}")
            except KeyboardInterrupt:
                print(f"\n\nProcess interrupted by user while processing {language}. Stopping execution.")
                sys.exit(0)
            except Exception as e:
                error_message = str(e)
                if "The language specified is not listed for localization" in error_message:
                    print(f"Skipping {language} ({locale}) - Language not supported by App Store")
                    continue
                else:
                    print(f"Error processing localization for {language}: {error_message}")
                    if hasattr(e, '__dict__'):
                        print(f"Full error details: {e.__dict__}")
            
            time.sleep(2)
            
        print("\nLocalization process completed!")
        print("Successfully processed app info and app store version localizations.")
        print("Note: Some localizations may have been skipped due to errors or conflicts.")
        print("Check the logs above for details on any issues encountered.")
