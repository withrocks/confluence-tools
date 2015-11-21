from jinja2 import PackageLoader, Environment
import logging


class ConfluenceContent:
    """Defines the content that will be created in Confluence"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        self.logger.debug("Initializing jinja2")
        self.jinja_env = Environment(loader=PackageLoader('confluence_tools', 'templates'),
                                     trim_blocks=True, lstrip_blocks=True)

    def get_diff_report_as_html(self, curr_version, prev_version, report, url):
        print report
        template = self.jinja_env.get_template('report.html')
        return template.render(include_summary=False,
                               has_changes=len(report) > 0,
                               current=curr_version,
                               previous=prev_version,
                               changes=report,
                               url=url)
