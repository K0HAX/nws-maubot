""" Maubot to get the weather from the National Weather Service and post in Matrix chat """

import logging
from re import IGNORECASE, Match, search, sub
from typing import Dict, Optional, Type, Union
from urllib.parse import urlencode

from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from yarl import URL

import xml.etree.ElementTree as ET

class Config(BaseProxyConfig):
    """Configuration class"""

    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("show_link")
        helper.copy("default_location")
        helper.copy("show_image")
        helper.copy("default_units")
        helper.copy("default_language")

class NwsBot(Plugin):
    """Maubot plugin class to get the weather and respond in a chat."""

    _service_url: str = "https://w1.weather.gov/xml/current_obs"
    _stored_language: str
    _stored_location: str
    _stored_units: str
    log = logging.getLogger(__name__)

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @command.new(
            name="wx", help="Get the weather",
            arg_fallthrough=False, require_subcommand=False
            )
    @command.argument("location", pass_raw=True)
    async def weather_handler(self, evt: MessageEvent, location: str) -> None:
        """
        Listens for `!weather` and returns a message with the result of
        a call to weather.gov for the location specified by `!weather <station>`
        or by the config file if no location is given
        """
        self._reset_stored_values()
        self._location(location)
        response = await self.http.get(self._url())
        response_text = await response.text()
        self.log.debug(response_text)
        wxdata = self._parse_xml(response_text)
        wxfmt = (f"[{wxdata.get('station_id')}] Location: {wxdata.get('location')}\\\n"
                 f"Weather: {wxdata.get('weather')}\\\n"
                 f"Temperature: {wxdata.get('temperature_string')}\\\n"
                 f"Relative Humidity: {wxdata.get('relative_humidity')}\\\n"
                 f"Wind: {wxdata.get('wind_string')}\\\n"
                 f"Dew Point: {wxdata.get('dewpoint_string')}\\\n"
                 f"Visibility (miles): {wxdata.get('visibility_mi')}"
                 )
        await evt.respond(self._message(wxfmt))
        #await self._image(evt)

    @weather_handler.subcommand("help", help="Usage instructions")
    async def help(self, evt: MessageEvent) -> None:
        """
        Return help message.
        """
        await evt.respond(
                "Get information about the weather from "
                "[weather.gov](https://weather.gov).\n\n"
                "If the location is not specified, the default wil be used by the server.\n\n"
                "Otherwise, location can be specified by Station ID:\\\n"
                "`!weather KSMP`\n\n"
                )

    def _base_url(self) -> URL:
        return URL(f"{self._service_url}/{self._location()}.xml")

    def _config_value(self, name: str) -> str:
        return (
                self.config[name].strip()
                if self.config[name] is not None
                else ""
                )

    def _location(self, location: str = "") -> str:
        """Return a cleaned-up location name"""
        if self._stored_location == "":
            location = location.strip()
            self._stored_location = (
                    location
                    if location
                    else self._config_value("default_location")
                    ).strip()

        return self._stored_location

    def _message(self, content: str) -> str:
        message: str = content
        location_match: Optional["Match[str]"] = search(r'^(.+):', message)

        if self.config["show_link"]:
            message += f"\n\n([weather.gov]({self._url()}))"

        return message

    def _options(self) -> Dict[str, Union[int, str]]:
        options: Dict[str, Union[int, str]] = {}

        if self._stored_language:
            options["lang"] = self._stored_language

        if self._stored_units:
            options[self._stored_units] = ""

        return options

    def _reset_stored_values(self) -> None:
        self._stored_language = ''
        self._stored_location = ''
        self._stored_units = ''

    def _url(self) -> str:
        return (f"{self._base_url()}")

    def _parse_xml(self, xmldata):
        # create element tree object
        tree = ET.fromstring(xmldata)

        self.log.debug(f"[tree] : {list(tree)}")

        # create empty dict for wx items
        wxdict = {}

        for child in tree:
            if child.tag == "image":
                continue
            if child.tag == "observation_time":
                continue
            wxdict[child.tag] = child.text

        return wxdict

