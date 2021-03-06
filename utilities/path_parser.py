# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import urllib2
import re
import urlparse
from logger import Logger


class PathParser(object):

    _DEBUG_BUILD_NAME = 'Debug'
    _ENGINEER_BUILD_NAME = 'Engineer'
    _USER_BUILD_NAME = 'User'
    _GAIA_GECKO = 'gaia + gecko'
    _GAIA = 'gaia'
    _GECKO = 'gecko'
    _IMAGES = 'images'

    def __init__(self):
        self.logger = Logger()

    def get_builds_list_from_url(self, url, status_callback=None):
        try:
            content = self._open_url(url)
            build_and_time_list = self._parse_build_and_time_from_html(content)
            return self._parse_device_version_and_time_from_list(build_and_time_list)
        except urllib2.HTTPError as e:
            self.logger.log('HTTP Error: ' + str(e.code) + ' ' + e.msg + ' of ' + url, status_callback=status_callback)
        except urllib2.URLError as e:
            self.logger.log('URL Error: ' + str(e.code) + ' ' + e.msg + ' of ' + url, status_callback=status_callback)

    def get_available_packages_from_url(self, base_url, build_src, build_id='', build_id_format=None, status_callback=None):
        packages = {}
        path = '/latest/'
        build_id = build_id.strip()
        if not build_id == '' and not build_id == 'latest':
            if self.verify_build_id(build_id, status_callback):
                path = self.get_path_of_build_id(build_id=build_id, build_id_format=build_id_format, status_callback=status_callback)
            else:
                self.logger.log('The build id [' + build_id + '] is not not valid.', status_callback=status_callback)
                return packages
        target_url = base_url + build_src + path
        self.logger.log('Get available packages list from ' + target_url, status_callback=status_callback)

        try:
            content = self._open_url(target_url)
            packages = self._parse_available_packages(build_src, content)
            # join the target_url and packages' basename
            for package_name, package_basename in packages.items():
                packages[package_name] = urlparse.urljoin(target_url, package_basename)
        except urllib2.HTTPError as e:
            self.logger.log('HTTP Error: ' + str(e.code) + ' ' + e.msg, status_callback=status_callback)
        except urllib2.URLError as e:
            self.logger.log('URL Error: ' + str(e.code) + ' ' + e.msg, status_callback=status_callback)
        return packages

    def _parse_available_packages(self, build_src, html_content):
        packages_dict = {}
        target_build_src = build_src
        for flag in ['debug', 'eng']:
            target_build_src = target_build_src.replace('-%s' % flag, '')
        splited_build_info = target_build_src.split('-', 2)
        device_name = splited_build_info[2]
        # Gecko pattern
        gecko_pattern = re.compile(
            '<a href="b2g-.*?.android-arm.tar.gz">(?P<gecko>b2g-.*?.android-arm.tar.gz)</a>',
            re.DOTALL | re.MULTILINE)
        # Gaia pattern
        gaia_pattern = re.compile(
            '<a href="gaia.zip">(?P<gaia>gaia.zip)</a>',
            re.DOTALL | re.MULTILINE)
        # Images package pattern
        images_pattern = re.compile(
            '<a href="' + device_name + '.zip">(?P<images>' + device_name + '.zip)</a>',
            re.DOTALL | re.MULTILINE)
        gecko = gecko_pattern.findall(html_content)
        gaia = gaia_pattern.findall(html_content)
        images = images_pattern.findall(html_content)
        if len(gecko) == 1:
            packages_dict.update({'gecko': gecko[0]})
        if len(gaia) == 1:
            packages_dict.update({'gaia': gaia[0]})
        if len(images) == 1:
            packages_dict.update({'images': images[0]})
        return packages_dict

    def _open_url(self, url):
        response = urllib2.urlopen(url)
        html = response.read()
        return html

    def _parse_build_and_time_from_html(self, html_content):
        build_and_time_pattern = re.compile(
            '<a href="(b2g|mozilla)-.*?-.*?/">(?P<build>(b2g|mozilla)-.*?-.*?)/</a></td><td align="right">(?P<time>.*?)\s*</td>',
            re.DOTALL | re.MULTILINE)
        build_and_time_list = build_and_time_pattern.findall(html_content)
        return build_and_time_list

    def _parse_device_version_and_time_from_list(self, build_and_time_list):
        root_dict = {}
        for build_and_time in build_and_time_list:
            # If the build name contains '-eng', then it is Engineer build.
            build_src = build_and_time[1]
            engineer_build = '-eng' in build_src
            # If the build name contains '-debug', then it is a debug build.
            debug_build = '-debug' in build_src
            # Remove flags
            target_build_src = build_src
            for flag in ('debug', 'eng'):
                target_build_src = target_build_src.replace('-%s' % flag, '')
            # Split string by '-'
            groups = target_build_src.split('-')
            splited_build_info = '-'.join(groups[:2]), '-'.join(groups[2:])
            device_name = splited_build_info[1]
            branch_name = splited_build_info[0]
            src_name = build_and_time[1]
            build = self._ENGINEER_BUILD_NAME if engineer_build else self._USER_BUILD_NAME
            if debug_build:
                build = ' '.join([build, self._DEBUG_BUILD_NAME])
            last_modify_time = build_and_time[2]
            build_item = {build: {'src': src_name, 'last_modify_time': last_modify_time}}

            if root_dict.get(device_name) == None:
                root_dict[device_name] = {}
            if root_dict[device_name].get(branch_name) == None:
                root_dict[device_name][branch_name] = {}
            root_dict[device_name][branch_name].update(build_item)
        return root_dict

    def verify_build_id(self, build_id, status_callback=None):
        build_id_without_dash = re.sub(r'\D', '', build_id)
        if not len(build_id_without_dash) == 14:
            return False
        else:
            return True

    def get_path_of_build_id(self, build_id, build_id_format=None, status_callback=None):
        build_id_without_dash = re.sub(r'\D', '', build_id)
        year = build_id_without_dash[0:4]
        month = build_id_without_dash[4:6]
        day = build_id_without_dash[6:8]
        hour = build_id_without_dash[8:10]
        min = build_id_without_dash[10:12]
        sec = build_id_without_dash[12:14]
        if build_id_format is  None:
            build_id_format = '/{year}/{month}/{year}-{month}-{day}-{hour}-{min}-{sec}/'
        path_of_build_id = build_id_format.format(year=year, month=month, day=day, hour=hour, min=min, sec=sec)
        self.logger.log('The path of build id is: ' + path_of_build_id, status_callback=status_callback)
        return path_of_build_id
