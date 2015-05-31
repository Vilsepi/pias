#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import config
import re
import dataset
import json
from flask import Flask, request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

db = dataset.connect(config.database_path)
app = Flask(__name__)


def _c(config_variable):
    '''Helper to get remote-specific strings.'''
    return config.remote_config[config_variable]


class Dialog:
    '''Remote site dialog. Always has text and close button,
    sometimes also has confirm button and title.'''

    def __init__(self, driver, dialog):
        self.title = dialog.find_element_by_id(_c('dialog_title')).text.encode('utf-8')
        self.text = dialog.find_element_by_id(_c('dialog_text')).text.encode('utf-8')
        self.confirm_button = WebDriverWait(
            driver,
            config.max_wait).until(
                EC.presence_of_element_located((By.ID, _c('dialog_submit'))))
        self.close_button = WebDriverWait(
            driver,
            config.max_wait).until(
                EC.presence_of_element_located((By.ID, _c('dialog_close'))))

    def confirm(self):
        self.confirm_button.click()

    def close(self):
        self.close_button.click()

    def __str__(self):
        return "{}{}{}{}".format(self.title, self.text, self.confirm_button, self.close_button)


class Bot:
    '''Bot that interacts with the remote site.'''

    def __init__(self):
        self.driver = webdriver.Firefox()
        self.driver.maximize_window()

    def get_url(self, url, run_smoke_tests=True):
        '''Load remote site '''

        self.driver.get(url)
        if run_smoke_tests:
            assert self.driver.title == config.remote_smoke_title
        return True

    def query(self, query_string):
        '''Run a query at the remote, return list of results.'''

        search_field_element = WebDriverWait(
            self.driver,
            config.max_wait).until(
                EC.presence_of_element_located((By.ID, _c('search_field'))))
        search_field_element.send_keys(query_string.decode('utf-8') + u'\n')
        return self.driver.find_elements_by_tag_name(_c('search_result'))

    def request_item(self, item):
        '''Interact with an item, return success boolean.'''

        try:
            item.click()
            dialog1 = Dialog(
                self.driver,
                WebDriverWait(self.driver, config.max_wait).until(
                    EC.presence_of_element_located((By.ID, _c('dialog_element')))))
            if dialog1.title == _c('dialog_assert_can_submit'):
                dialog1.confirm()
                dialog2 = Dialog(
                    self.driver,
                    WebDriverWait(self.driver, config.max_wait).until(
                        EC.presence_of_element_located((By.ID, _c('dialog_element')))))

                result = re.search(_c('dialog_assert_request_accepted_regex'), dialog2.text)
                if result:
                    position = result.group(1)
                    eta = result.group(2)
                    log.info('Request was accepted, position: {} eta: {}'.format(position, eta))
                    return True
                elif _c('dialog_assert_try_later') in dialog2.text:
                    log.info('This item cannot be requested right now')
                elif _c('dialog_assert_service_down') in dialog2.text:
                    log.info('Remote service is currently down')
                else:
                    log.error(dialog2)
                dialog2.close()
            else:
                log.error(dialog1)
                dialog1.close()
        except NoSuchElementException as e:
            logging.exception("Item request failed")
        return False

    def find_item_from_query_results(self, results, wanted, strict_matching=True):
        '''Scan through result set from a query and look for wanted item.
        Return item if found, otherwise return none.'''

        for result in results:
            try:
                title = result.find_element_by_tag_name(_c('search_result_title')).text.encode('utf-8')
                subtitle = result.find_element_by_tag_name(_c('search_result_subtitle')).text.encode('utf-8')

                log.debug('Comparing {0}/{1} with wanted {2}/{3}'.format(
                    title, subtitle, wanted.get('title').encode('utf-8'), wanted.get('subtitle').encode('utf-8')))
                if strict_matching:
                    if title == wanted.get('title').encode('utf-8') and subtitle == wanted.get('subtitle').encode('utf-8'):
                        log.info('Found exact match! {0} - {1}'.format(title, subtitle))
                        return result
                else:
                    raise NotImplementedError('Fuzzy matching not implemented')
            except NoSuchElementException as e:
                if result.get_attribute(_c('search_result_skippable_attribute')) != _c('search_result_skippable_value'):
                    logging.exception("Unknown element in results list")
        return None

bot = Bot()


@app.route('/', methods=['GET'])
def root():
    return 'GET /go\nGET /requests\nPOST /requests'

@app.route('/requests', methods=['GET','POST'])
def requests():
    if request.method == 'GET':
        return json.dumps([i for i in db['requests']])
    elif request.method == 'POST':
        request_payload = request.get_json(force=True)
        success_count = 0
        try:
            for payload_item in request_payload:
                db['requests'].insert(dict(
                    title=payload_item.get('title'),
                    subtitle=payload_item.get('subtitle'),
                    requested_from_remote=False))
                success_count += 1
            return "Added {} requests to queue".format(success_count)
        except:
            log.error('Failed when receiving requests')
            return "Failed"

@app.route('/go', methods=['GET'])
def go():
    if bot.get_url(config.remote_url):
        if config.unoptimized_searching:
            item = db['requests'].find_one(requested_from_remote=False)
            if not item:
                return 'No unmade requests in the queue'

            query_results = bot.query('{} {}'.format(item['title'].encode('utf-8'), item['subtitle'].encode('utf-8')))

            if bot.request_item(bot.find_item_from_query_results(query_results, item, config.strict_matching)):
                log.debug('Request was accepted.')
                return 'Request was accepted'
            else:
                return 'Failed'
        else:
            raise NotImplementedError('Optimized searching not implemented')
    else:
        return 'Failed'


if(__name__ == "__main__"):
    app.run(host=config.webserver_host, port=config.webserver_port, debug=config.webserver_debug)
