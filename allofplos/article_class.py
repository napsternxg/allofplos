import lxml.etree as et
import os

from transformations import (filename_to_doi, EXT_URL_TMP, INT_URL_TMP)
from plos_regex import (validate_doi, validate_filename, corpusdir)
from samples.corpus_analysis import parse_article_date


class Article:
    plos_prefix = ''

    def __init__(self, doi, directory=None):
        self.doi = doi
        if directory is None:
            self.directory = corpusdir
        else:
            self.directory = directory
        self._tree = None
        self._local = None

    @property
    def doi(self):
        return self._doi

    @doi.setter
    def doi(self, d):
        if validate_doi(d) is False:
            raise Exception("Invalid format for PLOS DOI")
        self._doi = d

    def get_path(self):
        if 'annotation' in self.doi:
            article_path = os.path.join(self.directory, 'plos.correction.' + self.doi.split('/')[-1] + '.xml')
        else:
            article_path = os.path.join(self.directory, self.doi.lstrip('10.1371/') + '.xml')
        return article_path

    def get_local_bool(self):
        article_path = self.get_path()
        return os.path.isfile(article_path)

    def get_local_element_tree(self, article_path=None):
        if article_path is None:
            article_path = self.get_path()
        if self.local:
            local_element_tree = et.parse(article_path)
            return local_element_tree
        else:
            print("Local article file not found: {}".format(article_path))

    def get_local_root_element(self, article_tree=None):
        if article_tree is None:
            article_tree = self.tree
        root = article_tree.getroot()
        return root

    def get_local_xml(self, article_tree=None, pretty_print=True):
        if article_tree is None:
            article_tree = self.tree
        local_xml = et.tostring(article_tree,
                                method='xml',
                                encoding='unicode',
                                pretty_print=pretty_print)
        return print(local_xml)

    def get_url(self, plos_network=False):
        URL_TMP = INT_URL_TMP if plos_network else EXT_URL_TMP
        return URL_TMP.format(self.doi)

    def get_remote_element_tree(self, url=None):
        if url is None:
            url = self.get_url()
        remote_element_tree = et.parse(url)
        return remote_element_tree

    def get_remote_xml(self, article_tree=None, pretty_print=True):
        if article_tree is None:
            article_tree = self.get_remote_element_tree()
        remote_xml = et.tostring(article_tree,
                                 method='xml',
                                 encoding='unicode',
                                 pretty_print=pretty_print)
        return print(remote_xml)

    def get_element_xpath(self, article_root=None, tag_path_elements=None):
        """
        For a local article's root element, grab particular sub-elements via XPath location
        Defaults to reading the element location for uncorrected proofs/versions of record
        :param article_root: the xml file for a single article
        :param tag_path_elements: xpath location in the XML tree of the article file
        :return: list of elements with that xpath location
        """
        if article_root is None:
            article_root = self.root
        if tag_path_elements is None:
            tag_path_elements = ('/',
                                 'article',
                                 'front',
                                 'article-meta',
                                 'custom-meta-group',
                                 'custom-meta',
                                 'meta-value')
        tag_location = '/'.join(tag_path_elements)
        return article_root.xpath(tag_location)

    def get_proof_status(self):
        """
        For a single article in a directory, check whether it is an 'uncorrected proof' or a
        'VOR update' to the uncorrected proof, or neither
        :return: proof status if it exists; otherwise, None
        """
        xpath_results = self.get_element_xpath()
        for result in xpath_results:
            if result.text == 'uncorrected-proof':
                return 'uncorrected_proof'
            elif result.text == 'vor-update-to-uncorrected-proof':
                return 'vor_update'
            else:
                pass
        return None

    def get_plos_journal(self, caps_fixed=True):
        """
        For an individual PLOS article, get the journal it was published in.
        :param caps_fixed: whether to render 'PLOS' in the journal name correctly or as-is ('PLoS')
        :return: PLOS journal at specified xpath location
        """
        try:
            journal = self.get_element_xpath(tag_path_elements=["/",
                                                                "article",
                                                                "front",
                                                                "journal-meta",
                                                                "journal-title-group",
                                                                "journal-title"])
            journal = journal[0].text
        except IndexError:
            # Need to file JIRA ticket: only affects pone.0047704
            journal_meta = self.get_element_xpath(tag_path_elements=["/",
                                                                     "article",
                                                                     "front",
                                                                     "journal-meta"])
            for journal_child in journal_meta[0]:
                if journal_child.attrib['journal-id-type'] == 'nlm-ta':
                    journal = journal_child.text
                    break

        if caps_fixed:
            journal = journal.split()
            if journal[0].lower() == 'plos':
                journal[0] = "PLOS"
            journal = (' ').join(journal)
        return journal

    def get_article_title(self):
        """
        For an individual PLOS article, get its title.
        :return: string of article title at specified xpath location
        """
        title = self.get_element_xpath(tag_path_elements=["/",
                                                          "article",
                                                          "front",
                                                          "article-meta",
                                                          "title-group",
                                                          "article-title"])
        title_text = et.tostring(title[0], encoding='unicode', method='text', pretty_print=True)
        return title_text.rstrip('\n')
    
    def get_dates(self, string_=False, string_format='%Y-%m-%d', debug=False):
        """
        For an individual article, get all of its dates, including publication date (pubdate), submission date
        :return: tuple of dict of date types mapped to datetime objects for that article, dict for date strings if wrong order
        """
        dates = {}

        tag_path_1 = ["/",
                      "article",
                      "front",
                      "article-meta",
                      "pub-date"]
        element_list_1 = self.get_element_xpath(tag_path_elements=tag_path_1)
        for element in element_list_1:
            pub_type = element.get('pub-type')
            try:
                date = parse_article_date(element)
            except ValueError:
                print('Error getting pubdates for {}'.format(self.doi))
                date = ''
            dates[pub_type] = date

        tag_path_2 = ["/",
                      "article",
                      "front",
                      "article-meta",
                      "history"]
        element_list_2 = self.get_element_xpath(tag_path_elements=tag_path_2)
        for element in element_list_2:
            for part in element:
                date_type = part.get('date-type')
                try:
                    date = parse_article_date(part)
                except ValueError:
                    print('Error getting history dates for {}'.format(self.doi))
                    date = ''
                dates[date_type] = date
        if debug:
            # check whether date received is before date accepted is before pubdate
            if dates.get('received', '') and dates.get('accepted', '') in dates:
                if not dates['received'] <= dates['accepted'] <= dates['epub']:
                    print('{}: dates in wrong order'.format(self.doi))

        if string_:
            # can return dates as strings instead of datetime objects if desired
            for key, value in dates.items():
                if value:
                    dates[key] = value.strftime(string_format)

        return dates

    def get_pubdate(self, string_=False, string_format='%Y-%m-%d'):
        dates = self.get_dates(string_=string_, string_format=string_format)
        return dates['epub']
    
    def get_corresponding_author_info(self):
        tag_path_1 = ["/",
                      "article",
                      "front",
                      "article-meta",
                      "contrib-group"]
        contrib_groups = self.get_element_xpath(tag_path_elements=tag_path_1)
        corr_rid = ''
        given_names = ''
        surname = ''
        corr_authors = {}
        for group in contrib_groups:
            for contrib in group:
                try:
                    if contrib.attrib['contrib-type'] == "author" and contrib.attrib['corresp'] ==  "yes":
                        contrib_elements = contrib.getchildren()
                        for element in contrib_elements:
                            if element.tag == 'xref' and element.attrib['ref-type'] == 'corresp':
                                corr_rid = element.attrib['rid']
                                corr_author_elem = contrib
                                corr_name_element = contrib.find("name")
                                for name_element in corr_name_element.getchildren():
                                    if name_element.tag == 'surname':
                                        # for some reason, name_element.text doesn't work for this element
                                        surname = et.tostring(name_element, encoding='unicode', method='text').rstrip('\n')
                                    elif name_element.tag == 'given-names':
                                        given_names = name_element.text
                                        if given_names == '':
                                            print("given names element.text didn't work")
                                            given_names = et.tostring(name_element, encoding='unicode', method='text').rstrip('\n')
                            else:
                                pass
                except KeyError:
                    pass
#         if corr_rid and surname == '':
#             return print('No corr author information found for {}, {}'.format(self.doi, self.type_))
        if corr_rid:
            corr_authors[corr_rid] = {'last': surname, 'first': given_names}
            tag_path_2 = ["/",
                          "article",
                          "front",
                          "article-meta",
                          "author-notes"]
            author_notes = self.get_element_xpath(tag_path_elements=tag_path_2)
            for note in author_notes:
                if note.tag == 'corresp':
                    author_info = note.getchildren()
                    print(author_info)
                    for item in author_info:
                        print(author_info.text)
                else:
                    try:
                        if note.attrib['id'] == corr_rid:
                            print(et.tostring(note, encoding='unicode', method='text').rstrip('\n'))
                    except KeyError:
                        pass
            
            return corr_authors
        else:
            return print('No corr author element found for {}, {}'.format(self.doi, self.type_))

    def get_jats_article_type(self):
        """
        For an article file, get its JATS article type
        Use primarily to find Correction (and thereby corrected) articles
        :return: JATS article_type at that xpath location
        """
        type_element_list = self.get_element_xpath(tag_path_elements=["/",
                                                                      "article"])
        return type_element_list[0].attrib['article-type']

    def get_plos_article_type(self):
        """
        For an article file, get its PLOS article type. This format is less standardized than JATS article type
        :return: PLOS article_type at that xpath location
        """
        article_categories = self.get_element_xpath(tag_path_elements=["/",
                                                                       "article",
                                                                       "front",
                                                                       "article-meta",
                                                                       "article-categories"])
        subject_list = article_categories[0].getchildren()

        for i, subject in enumerate(subject_list):
            if subject.get('subj-group-type') == "heading":
                subject_instance = subject_list[i][0]
                s = ''
                for text in subject_instance.itertext():
                    s = s + text
                    plos_article_type = s
        return plos_article_type

    def get_dtd(self):
        """
        For more information on these DTD tagsets, see https://jats.nlm.nih.gov/1.1d3/ and https://dtd.nlm.nih.gov/3.0/
        """
        try:
            dtd = self.get_element_xpath(tag_path_elements=["/",
                                                            "article"])
            dtd = dtd[0].attrib['dtd-version']
            if str(dtd) == '3.0':
                dtd = 'NLM 3.0'
            elif dtd == '1.1d3':
                dtd = 'JATS 1.1d3'
        except KeyError:
            print('Error parsing DTD from', self.doi)
            dtd = 'N/A'
        return dtd

    @property
    def xml(self):
        return self.get_local_xml()

    @property
    def tree(self):
        if self._tree is None:
            return self.get_local_element_tree()
        else:
            return self._tree

    @property
    def root(self):
        return self.get_local_root_element()

    @property
    def url(self):
        return self.get_url(plos_network=self.plos_network)

    @property
    def filename(self):
        return self.get_path()

    @property
    def local(self):
        if self._local is None:
            return self.get_local_bool()
        else:
            return self._local

    @property
    def proof(self):
        return self.get_proof_status()

    @property
    def journal(self):
        return self.get_plos_journal()

    @property
    def title(self):
        return self.get_article_title()

    @property
    def pubdate(self):
        return self.get_pubdate()

    @property
    def type_(self):
        return self.get_jats_article_type()

    @property
    def plostype(self):
        return self.get_plos_article_type()

    @property
    def dtd(self):
        return self.get_dtd()

    @filename.setter
    def filename(self, value):
        self.doi = filename_to_doi(value)

    @classmethod
    def from_filename(cls, filename):
        return cls(filename_to_doi(filename))