#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import config
import re
from flask import Flask
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

app = Flask(__name__)

def _c(config_variable):
    return config.remote_config[config_variable]

class Dialog:

    def __init__(self, dialog_element, driver):
        self.title = dialog_element.find_element_by_id(_c('dialog_title')).text.encode('utf-8')
        self.text = dialog_element.find_element_by_id(_c('dialog_text')).text.encode('utf-8')
        self.confirm_button = WebDriverWait(driver, config.max_wait).until(EC.presence_of_element_located((By.ID, _c('dialog_submit'))))
        self.close_button = WebDriverWait(driver, config.max_wait).until(EC.presence_of_element_located((By.ID, _c('dialog_close'))))

    def confirm(self):
        self.confirm_button.click()

    def close(self):
        self.close_button.click()

    def __str__(self):
        return "{}{}{}{}".format(self.title, self.text, self.confirm_button, self.close_button)


class Bot:

    def __init__(self):
        self.driver = webdriver.Firefox()
        self.driver.maximize_window()

    def get_url(self, url, run_smoke_tests=True):
        self.driver.get(url)
        if run_smoke_tests:
            assert self.driver.title == config.remote_smoke_title
        return True

    def query(self, query_string):
        search_field_element = WebDriverWait(self.driver, config.max_wait).until(EC.presence_of_element_located((By.ID, _c('search_field'))))
        search_field_element.send_keys(query_string + '\n')
        return self.driver.find_elements_by_tag_name(_c('search_result'))

    def _request_item(self, item):
        try:
            item.click()
            dialog1 = Dialog(WebDriverWait(self.driver, config.max_wait).until(EC.presence_of_element_located((By.ID, _c('dialog_element')))), self.driver)
            if dialog1.title == _c('dialog_assert_can_submit'):
                dialog1.confirm()
                dialog2 = Dialog(WebDriverWait(self.driver, config.max_wait).until(EC.presence_of_element_located((By.ID, _c('dialog_element')))), self.driver)
                result = re.search(_c('dialog_assert_request_accepted_regex'), dialog2.text)
                if result:
                    position = result.group(1)
                    eta = result.group(2)
                    log.info('Request was accepted, position: {} eta: {}'.format(position, eta))
                else:
                    if _c('dialog_assert_try_later') in dialog2.text:
                        log.info('This item cannot be requested right now')
                    else:
                        log.error(dialog2)
                dialog2.close()
            else:
                log.error(dialog1)
                dialog1.close()
            return True

        except NoSuchElementException as e:
            logging.exception("Item request failed")

    def interact_with_results(self, results, wanted_items, strict_matches_only=True, interaction_quota=3):
        for result in results:
            try:
                title = result.find_element_by_tag_name(_c('search_result_title')).text.encode('utf-8')
                body = result.find_element_by_tag_name(_c('search_result_body')).text.encode('utf-8')

                for wanted in wanted_items:
                    log.debug('Comparing {0}/{1} with wanted {2}/{3}'.format(title, body, wanted.get('title'), wanted.get('body')))
                    if title == wanted.get('title') and body == wanted.get('body'):
                        log.info('Found exact match! {0} - {1}'.format(title, body))
                        self._request_item(result)

            except NoSuchElementException as e:
                if result.get_attribute(_c('search_result_skippable_attribute')) != _c('search_result_skippable_value'):
                    logging.exception("Unknown element in results list")


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
