import json
import logging
import sys
import time
from datetime import datetime
from string import Template
from types import FunctionType
from typing import List
from xmlrpc.client import Boolean

import requests
import schedule

from emailer import Emailer

FORMAT = '[%(levelname)s] %(asctime)s %(message)s'

log = logging.getLogger("ind-poller-logger")
logging.basicConfig(level=logging.INFO, format=FORMAT,datefmt="%Y-%m-%d %H:%M:%S")

# {"status": "OK", "data": [{"key":"6284e2f0bf3dcb816618b965b4ae74d0","date":"2022-04-22","startTime":"09:00","endTime":"09:10","parts":1}] }
if len(sys.argv) != 4:
    raise Exception("usage: python ind_poll.py <sender> <receiver> <password>")

sender = sys.argv[1]
pwd = sys.argv[3]
to = sys.argv[2]

emailer = Emailer("smtp.gmail.com", 465, sender, pwd)
url_template = Template("https://oap.ind.nl/oap/api/desks/${code}/slots/?productKey=BIO&persons=1")

notified_keys = list()


class Site:
    name: str
    url: str
    filter: FunctionType

    def __init__(self, name: str, url: str, filter=lambda x: True):
        self.name = name
        self.url = url
        self.filter = filter

    def __str__(self):
        return f"Site({self.name}) [ url={self.url} ] "



class DataPoint:
    # {"key":"6284e2f0bf3dcb816618b965b4ae74d0","date":"2022-04-22","startTime":"09:00","endTime":"09:10","parts":1}
    def __init__(self, site_name: str):
        self.site_name = site_name

    def parse(self, data):
        self.key = data["key"]
        self.date = datetime.strptime(data["date"], "%Y-%m-%d")
        self.start_time = data["startTime"]
        self.end_time = data["endTime"]
        self.parts = data["parts"]

    def __str__(self):
        return f"DataPoint({self.site_name}) [ key={self.key} date={self.date.date()} start_time={self.start_time} end_time={self.end_time} parts={self.parts} ]"

def is_weekend(dp: DataPoint) -> Boolean:
    return dp.date.weekday() > 4


def poll() -> List[DataPoint]:
    sites = [
        Site(name="Utrecht", url=url_template.substitute(code="UT")),
        Site(name="Expatcenter Utrecht", url=url_template.substitute(code="fa24ccf0acbc76a7793765937eaee440")),
        Site(name="Den Haag", url=url_template.substitute(code="DH"), filter=is_weekend),
        Site(name="Amsterdam", url=url_template.substitute(code="AM"), filter=is_weekend),
        Site(name="Rotterdam", url=url_template.substitute(code="RO"), filter=is_weekend),
    ]

    available = list()

    for site in sites:
        log.debug("checking %s", site)
        try:
            resp = requests.get(site.url)

            if resp.status_code == 200:
                content = json.loads(resp.text[5:])
                if content["status"] == "OK":
                    data = content["data"]

                    for value in data:
                        dp = DataPoint(site.name)
                        dp.parse(value)
                        if site.filter(dp) and dp.key not in notified_keys:
                            log.debug("found %s", dp)
                            available.append(dp)
                        else:
                            log.debug("filtered %s", dp)
                else:
                    log.error("status bad %s (%s): %s", site.name, site.url, data["status"])
            else:
                log.error("poll failed %s (%s)", site.name, site.url)
        except Exception:
            log.exception("failed to connect to site %s (%s)", site.name, site.url)

    return available


def notify(available: List[DataPoint]):
    body = """
    <html>
    <body>
        <p>Hi B,<br>
        The following booking became available:<br><br>
    """
    for a in available:
        body += f"{a.date.date()} at {a.start_time} in {a.site_name}<br>"

    body += """
        </p>
        <a href="https://oap.ind.nl/oap/en/#/BIO">Book here</a>
    </body>
    </html>
    """

    log.info("sending %i options", len(available))
    emailer.send(to, "IND appointment availability", str(available), body)
    emailer.send(sender, "IND appointment availability", str(available), body)
    for a in available:
        notified_keys.append(a.key)
    log.debug("notified [%s]", notified_keys)


def job():
    available = poll()
    if len(available) > 0:
        notify(available)

job()
schedule.every(60).seconds.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
