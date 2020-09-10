#! /bin/env python
from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.parse import urlencode
import os
import re
import sys
# import icalendar
from datetime import datetime
import time
import yaml

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# check_euclid_url sanity checks that real_url looks like a proper link to DRPS
def check_euclid_url(code: str, real_url: str):
    # Yes, unfortunately DRPS only supports HTTP. and not HTTPS.
    # The University of Edinburgh, everyone.
    prefix_len = len("http://www.drps.ed.ac.uk/")

    # This plucks out the "16-17" from e.g. http://www.drps.ed.ac.uk/16-17/dpt/cxinfr08013.htm
    year = real_url[prefix_len:prefix_len+5]

    # Now we recreate the URL
    expected_euclid_url = f"http://www.drps.ed.ac.uk/{year}/dpt/cx{code.lower()}.htm"

    # And do an assertion
    if real_url != expected_euclid_url:
        eprint(f"Expected to see something like {expected_euclid_url}")
        eprint(f"Got this instead: {real_url}")
        sys.exit(1)

def deep_equals(left: dict, right: dict):
    return yaml.safe_dump(left) == yaml.safe_dump(right)

class Course(object):

    def __init__(self, soup):
        fields = soup.find_all("td")
        #print(fields)
        self.name = fields[0].text

        euclid_ele = fields[1]
        self.euclid_code = euclid_ele.text
        self.euclid_url = fields[1].find("a", href=True)["href"]
        check_euclid_url(self.euclid_code, self.euclid_url)

        self.acronym = fields[2].text
        self.level = int(fields[9].text)
        self.credits = int(fields[10].text)
        self.year = int(fields[11].text)
        self.delivery = fields[12].text
        self.diet = fields[13].text

        if self.delivery == "S1":
            self.delivery_ordinal = 1
        elif self.delivery == "S2":
            self.delivery_ordinal = 2
        elif self.delivery == "YR":
            self.delivery_ordinal = 3
        else:
            self.delivery_ordinal = 4

        ratio = fields[14].text
        if ratio == "":
            self.cw_exam_ratio = None
        else:
            assert ratio.count("/") == 1
            cw, exam = map(int, ratio.split("/"))
            self.cw_exam_ratio = [cw, exam]

    def build_fields(self):
        return {
            'name': self.name,
            'euclid_code': self.euclid_code,
            'euclid_url': self.euclid_url,
            'acronym': self.acronym,
            'level': self.level,
            'credits': self.credits,
            'delivery': self.delivery,
            'delivery_ordinal': self.delivery_ordinal,
            'year': int(self.year),
            'diet': self.diet,
            'cw_exam_ratio': self.cw_exam_ratio
        }

    def __str__(self):
        return "{name}\t\t\t\t{acronym} ({euclid_code})\t\t{delivery}\t\t{diet}\t\t{cw_exam_ratio}\t\tLevel {level}, {credits} credits".format(
            name=self.name,
            acronym=self.acronym,
            euclid_code=self.euclid_code,
            delivery=self.delivery,
            diet=self.diet,
            cw_exam_ratio=self.cw_exam_ratio,
            level=self.level,
            credits=self.credits
        )


def main():
    usock = urlopen("http://course.inf.ed.ac.uk")

    b = BeautifulSoup(usock.read(), "html.parser")
    cTable = b.find('table', attrs={'class': 'course sortable'})
    cBody = cTable.find("tbody")
    rows = cBody.find_all('tr')

    courses = list(map(Course, rows))

    dump_yaml = False
    if len(sys.argv) > 1:
        dump_yaml = sys.argv[1] == "--dump-yaml"
        dump_codes = sys.argv[1] == "--dump-codes"
        yaml_target = None
        if sys.argv[1] == "--auto-yaml":
            dump_yaml = True
            yaml_target = sys.argv[2]
    else:
        # This checks to make sure that any courses with an empty field
        # for exam diet has a cw_exam_ratio of "100/0"
        non_conform = False
        for course in courses:
            if (course.diet == "") and (course.cw_exam_ratio != "100/0"):
                if not non_conform:
                    non_conform = True
                    print("Issue: Empty exam diets without defined cw_exam_ratio:")
                    print("acronym (euclid)\t\tdelivery\t\tdiet\t\tratio")
                print(course)


        print()
        print()
        print("Call again with --dump-yaml to print out YAML")
        print("Call again with --dump-codes year to print out the INFR codes for that year")
        print("Call again with --auto-yaml <filename> to read the file, compare contents, update the file, and print stuff out for GitHub Actions")
        return

    if dump_yaml:
        infoNode = b.find("p", attrs={'class': 'info noprint'})
        lastUpdate= infoNode.find("span", attrs={'class': 'date'}).text

        out = ""
        out += "# This document was automatically generated\n"
        out += "# using data from http://course.inf.ed.ac.uk\n"
        out += "#\n"
        out += f"# Last update: {lastUpdate}\n\n"

        courses_out = {}
        for course in courses:
            courses_out[course.acronym.lower()] = course.build_fields()

        data = {}
        data['list'] = courses_out
        data['last_update'] = lastUpdate

        out += yaml.safe_dump(data, default_flow_style=False)

        if yaml_target == None:
            print(out)
            return

        if not os.path.isfile(yaml_target):
            eprint(f"File {yaml_target} does not exist.")
            sys.exit(1)
            return

        with open(yaml_target, "r") as f:
            old_data = yaml.safe_load(f)

        # Docs:
        # - https://github.community/t/perform-next-job-if-specific-step-of-previous-job-was-success/17329/2?u=qaisjp
        # - https://github.community/t/support-saving-environment-variables-between-steps/16230/2?u=qaisjp
        # - https://docs.github.com/en/actions/reference/workflow-commands-for-github-actions#setting-an-output-parameter
        has_changed = not deep_equals(old_data['list'], data['list'])
        has_changed_str = str(has_changed).lower()
        print(f"::set-output name=has_changed::{has_changed_str}")

        eprint(f"courses.yaml changed? {has_changed_str}")

        with open(yaml_target, "w") as f:
            f.write(out)


    elif dump_codes:
        year = int(sys.argv[2])
        diets = sys.argv[3:]


        codes = []
        for course in courses:
            if course.year == year:
                # print(course.year, course.euclid_code, course.diet)
                print(course.euclid_code, end=" ")

    else:
        print("Unknown arg provided.")
        return


main()
