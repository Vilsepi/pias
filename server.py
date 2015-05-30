#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import config
from flask import Flask
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

app = Flask(__name__)

def _c(config_variable):
    return config.remote_config.get(config_variable)

class Bot:

    def __init__(self):
        self.driver = webdriver.Firefox()
        self.driver.maximize_window()

    def get_url(self, url, run_smoke_tests=True):
        self.driver.get(url)
        if run_smoke_tests:
            assert config.remote_smoke_title == self.driver.title
        return True

    def query(self, query_string):
        search_field_element = WebDriverWait(self.driver, 10).until(lambda driver: self.driver.find_element_by_id(_c('search_field')))
        search_field_element.send_keys(query_string + '\n')
        return self.driver.find_elements_by_tag_name(_c('search_result'))

    def interact_with_result(self, result):
        result.click()

        dialog_element = WebDriverWait(self.driver, 5).until(lambda driver: self.driver.find_element_by_id(_c('dialog_element')))
        dialog_title = dialog_element.find_element_by_id(_c('dialog_title')).text.encode('utf-8')
        dialog_text = dialog_element.find_element_by_id(_c('dialog_text')).text.encode('utf-8')
        dialog_confirm = dialog_element.find_element_by_id(_c('dialog_confirm'))
        dialog_cancel = dialog_element.find_element_by_id(_c('dialog_cancel'))

        return True

    def interact_with_results(self, results, wanted_items, strict_matches_only=True, interaction_quota=3):
        for result in results:
            try:
                title = result.find_element_by_tag_name(_c('search_result_title')).text.encode('utf-8')
                body = result.find_element_by_tag_name(_c('search_result_body')).text.encode('utf-8')

                for wanted in wanted_items:
                    log.debug('Comparing {0}/{1} with wanted {2}/{3}'.format(title, body, wanted.get('title'), wanted.get('body')))
                    if title == wanted.get('title') and body == wanted.get('body'):
                        log.info('Found exact match! {0} - {1}'.format(title, body))
                        self.interact_with_result(result)

            except NoSuchElementException as e:
                if result.get_attribute(_c('search_result_skippable_attribute')) != _c('search_result_skippable_value'):
                    log.warn(e)


@app.route('/', methods=['GET'])
def root():
    bot = Bot()

    if bot.get_url(config.remote_url):
        results = bot.query('kee')
        bot.interact_with_results(results, config.wanted_items, config.strict_matches_only)
        return 'Done'
    else:
        return 'Failed'


if(__name__ == "__main__"):

    app.run(host=config.webserver_host, port=config.webserver_port, debug=config.webserver_debug)
