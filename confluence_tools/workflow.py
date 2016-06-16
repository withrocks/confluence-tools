import json
import os
from confluence_tools.content import ConfluenceContent
import logging


class Workflow:
    """
    Defines top-level actions in the documentation workflow
    """
    def __init__(self, provider, whatif, msg, logger=None):
        """
        Initializes the workflow with a provider that looks like
        a ConfluenceProvider
        """
        self.provider = provider
        self.whatif = whatif
        self.msg = msg
        self.logger = logger or logging.getLogger(__name__)

    def generate_metadata_and_upload(self, path, space, current, previous):
        # Generate a metadata file for the current version, ignored if it
        # already exists:
        self._generate_metadata_file(path, space, current)

        if previous:
            self._upload_report(space, path, current, previous)
            self.msg("Report has been uploaded")
        else:
            self.msg("Previous version not supplied, diff report will not be created")

    def _generate_metadata_file(self, path, space, current):
        current_metadata_file = self._get_version_file_path(path, space, current)
        if os.path.isfile(current_metadata_file):
            self.msg("A metadata file already exists for {} at {}".format(
                current, current_metadata_file))
        else:
            self.msg("Determining the metadata for version={},space={}...".format(current, space))
            current_metadata = list(self.provider.get_space_content_history(space))
            self.msg("Saving metadata in '{}'".format(current_metadata_file))

            if not self.whatif:
                with open(current_metadata_file, 'w') as f:
                    json.dump(current_metadata, f, sort_keys=True, indent=4)

    @staticmethod
    def _get_diff_report(current, previous):
        """Returns a diff report between current and previous version"""
        def by_id(dictionary):
            return {item["id"]: item for item in dictionary}

        current_by_id = by_id(current)
        previous_by_id = by_id(previous)

        both = set(current_by_id.keys()) & set(previous_by_id.keys())
        only_in_current = set(current_by_id.keys()) - set(previous_by_id.keys())
        only_in_previous = set(previous_by_id.keys()) - set(current_by_id.keys())

        changed_tuples = [(current_by_id[key], previous_by_id[key]) for key in both
                          if current_by_id[key]["version"] != previous_by_id[key]["version"]]
        new = [current_by_id[key] for key in only_in_current
               if key not in previous_by_id.keys()]
        deleted = [previous_by_id[key] for key in only_in_previous
                   if key not in current_by_id.keys()]

        changed = []
        for item in changed_tuples:
            item[0]["type"] = "changed"
            item[0]["previous"] = item[1]["version"]
            changed.append(item[0])
        for item in new:
            item["type"] = "new"
        for item in deleted:
            item["type"] = "deleted"

        report = changed + new + deleted
        return report

    def _upload_report(self, space, path, current, previous):
        """
        Uploads a report, uses generated version files
        that need to exist at ``path``
        """
        version_history_title = "Version History"
        page = self.provider.get_page(space, version_history_title)
        if not page:
            raise Exception("Missing page with title '{}'".format(version_history_title))
        version_history_id = page["id"]

        prev_metadata = self._load_version_file(path, space, previous)
        curr_metadata = self._load_version_file(path, space, current)

        self.logger.info("Generating diff report...")
        report = self._get_diff_report(curr_metadata, prev_metadata)

        self.logger.debug("Formatting diff report as html...")
        content = ConfluenceContent()
        html = content.get_diff_report_as_html(current, previous, report, self.provider.url)
        self.logger.debug("Generated html: {}".format(html))

        self.logger.info("Updating Confluence with latest info...")
        if not self.whatif:
            title = "Version {}".format(current)
            page = self.provider.get_page(space, title)

            if not page:
                self.provider.create_page(title, space, version_history_id, html)
            else:
                page_id = page["id"]
                self.provider.update_page(page_id, html)
        else:
            self.logger.info("Whatif: Not updating page")

    @staticmethod
    def _get_version_file_path(root, space, version):
        """Returns the full path to a version file"""
        return os.path.join(root, "confluence-{}-{}.version".format(space, version))

    def _load_version_file(self, root, space, version):
        """Loads a version file"""
        with open(self._get_version_file_path(root, space, version), 'r') as f:
            return json.load(f)
