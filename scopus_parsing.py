from selenium import webdriver
from selenium.webdriver.common.by import By
import lxml
from lxml.html import fromstring, tostring
from time import sleep
import json
from typing import Union, List
from selenium.webdriver import FirefoxOptions
import re


def save_json(data: Union[List[dict], dict], path: str):
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def get_first_element(elements: list):
    return elements[0] if len(elements) > 0 else None


def clear_text(text: str):
    if not text:
        return None

    return text.replace('\xa0', '').replace('•', '').strip()


def to_int(number: str):
    if not number:
        return None

    return int("".join(number.replace(',', "").split()))


class ArticleBlockParser:
    """
    Получение информации по статьям автора
    """

    @staticmethod
    def _authors_parse(authors_block) -> list:
        """
        
        :param authors_block: список всех соавторов публикации
        :return: список с информацией по каждому соавтору
        """
        authors = []

        for block in authors_block:
            author_block = fromstring(tostring(block))
            link = author_block.xpath('@href')[-1]
            authors.append({
                'Name': author_block.xpath('span/text()')[-1],
                'ID': get_first_element(re.findall(r'.+authorId=(\d+)+', link))
            })

        return authors

    def article_block_parse(self, block: lxml.html.HtmlElement) -> dict:
        """
        Общая информация по публикации
        :param block: часть сайта с информацией по конкретной публикации
        :return: словарь с информацией по публикации
        """
        type_ = block.xpath('//span[contains(@class, "article-type-line")]/text()')
        title = block.xpath('//div[starts-with(@class, "list-title")]/h4/span/text()')
        publisher = block.xpath('//a[contains(@class, "source-link")]/span[1]/text()')
        if not publisher:
            publisher = block.xpath('//div[contains(@data-component, "document-source")]/span[1]/text()')

        citations = block.xpath('//span[contains(@data-testid, "clickable-count")]/text()')

        authors = self._authors_parse(
            block.xpath('//a[starts-with(@href, "/authid/detail.uri?authorId=")]')
        )

        return {
            'Title': get_first_element(title),
            'Type': clear_text(get_first_element(type_)),
            'Publisher': get_first_element(publisher),
            'Citations': to_int(get_first_element(citations)),
            'Authors': authors
        }


class ScopusScraper(ArticleBlockParser):
    """
    Сбор информации по автору
    """

    def __init__(self):
        options = FirefoxOptions()
        options.add_argument('--headless')
        self.agent = webdriver.Firefox(executable_path=r'C:\Users\kosty\Desktop\geckodriver.exe', options=options)

    def get_general_info(self) -> dict:
        """
        Возвращает словарь с основной информацией об авторе
        :return: словарь с основной информацией об авторе
        """
        general_info = self.agent.find_element(by=By.XPATH, value=('//div[starts-with(@id, "scopus-author-profile") '
                                                           'and contains(@id, "general-information-content")]'))
        general_info = fromstring(general_info.get_attribute('innerHTML'))

        documents_panel = self.agent.find_element(by=By.XPATH, value='//div[@id="documents-panel"]')
        documents_panel = fromstring(documents_panel.get_attribute('innerHTML'))

        name = general_info.xpath('//h1/strong/text()')
        affiliation = general_info.xpath('//span[@data-testid="authorInstitution"]/a/span[1]/text()')
        id_ = general_info.xpath('//span[@data-testid="authorId"]/text()')
        orcid = general_info.xpath('//a[contains(@href, "orcid.org")]/span[2]/span/text()')
        citations = general_info.xpath('//div[@data-testid="metrics-section-citations-count"]/div/div/span/text()')
        co_authors_num = self.agent.find_element(by=By.XPATH, value='//button[@id="co-authors"]/span').text
        h_index = general_info.xpath('//div[@data-testid="metrics-section-h-index"]/div/div/span/text()')
        articles_num = documents_panel.xpath('//div[@data-testid="pill-author-profile--documents"]/div/span/text()')
        articles_num = re.findall(r'\d+', get_first_element(articles_num))
        co_authors_num = re.findall(r'\d+', co_authors_num)

        data = {
            'Name': get_first_element(name),
            'ID': get_first_element(id_),
            'ORCID': get_first_element(orcid),
            'Institute': get_first_element(affiliation),
            'Metrics': {
                'Citations': to_int(get_first_element(citations)),
                'Coauthors': to_int(get_first_element(co_authors_num)),
                'H_index': to_int(get_first_element(h_index)),
                'Articles': to_int(get_first_element(articles_num))
            }
        }

        return data

    def get_article_info(self) -> list:
        """
        Возвращает информацию по статьям
        :return: словарь с информацией по статьям
        """
        data = []

        article_blocks = self.agent.find_elements(by=By.XPATH, value='//li[@data-component="results-list-item"]')
        for item in article_blocks:
            data.append(
                self.article_block_parse(fromstring(item.get_attribute('innerHTML')))
            )

        return data

    async def parse(self, author_id: str, get_articles: bool) -> dict:
        """
        Сбор данных со страницы автора
        :param get_articles:
        :param author_id: id автора в Scopus
        :return: словарь с данными по автору
        """
        url = f'https://www.scopus.com/authid/detail.uri?authorId={author_id}&origin=recordpage'
        self.agent.get(url)
        sleep(2)

        general_info = self.get_general_info()

        if get_articles:
            general_info['Articles'] = self.get_article_info()



        return general_info



    def __del__(self):
        self.agent.close()


if __name__ == '__main__':
    scopus_id = '57213147038'
    parser = ScopusScraper()
    res = parser.parse(scopus_id)

    save_json(res, f'{scopus_id}.json')
