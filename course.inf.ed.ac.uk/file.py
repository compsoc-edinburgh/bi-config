#! /bin/env python
from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.parse import urlencode
import re
import sys
# import icalendar
from datetime import datetime
import time
import yaml

class Course(object):

    def __init__(self, soup):
        fields = soup.find_all("td")

        self.name = fields[0].text
    
        euclid_ele = fields[1]
        self.euclid_code = euclid_ele.text
        self.euclid_url = fields[1].find("a", href=True)["href"] # not used

        expected_euclid_url = "http://www.drps.ed.ac.uk/18-19/dpt/cx" + self.euclid_code.lower() + ".htm"
        assert self.euclid_url == expected_euclid_url

        self.acronym = fields[2].text
        self.year = int(fields[9].text)
        self.delivery = fields[10].text
        self.diet = fields[11].text

        ratio = fields[12].text
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
            'delivery': self.delivery,
            'year': int(self.year),
            'diet': self.diet,
            'cw_exam_ratio': self.cw_exam_ratio
        }

    def __str__(self):
        return "{name}\t\t\t\t{acronym} ({euclid_code})\t\t{delivery}\t\t{diet}\t\t{cw_exam_ratio}".format(
            name=self.name,
            acronym=self.acronym,
            euclid_code=self.euclid_code,
            delivery=self.delivery,
            diet=self.diet,
            cw_exam_ratio=self.cw_exam_ratio
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
        return

    if dump_yaml:
        infoNode = b.find("p", attrs={'class': 'info noprint'})
        lastUpdate= infoNode.find("span", attrs={'class': 'date'}).text

        print("# This document was automatically generated")
        print("# using data from http://course.inf.ed.ac.uk")
        print("#")
        print("# Last update:", lastUpdate)
        print()

        courses_out = {}
        for course in courses:
            courses_out[course.acronym.lower()] = course.build_fields()

        data = {}
        data['list'] = courses_out
        data['last_update'] = lastUpdate

        out = yaml.dump(data, default_flow_style=False)
        print(out)
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
