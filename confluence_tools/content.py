
class ConfluenceContent:
    """Defines the content that will be created in Confluence"""

    @staticmethod
    def get_diff_report_as_html(curr_version, prev_version, report, url):
        html = []
        # TODO: Move to template files
        version_table = """
        <table>
          <tbody>
            <tr>
              <th>Current version</th>
              <td colspan="1">{}</td>
            </tr>
          <tr>
            <th colspan="1">Previous version</th>
            <td colspan="1">{}</td>
          </tr>
          </tbody>
        </table>
        """.format(curr_version, prev_version)

        change_table_templ = """
        <table>
          <tbody>
            <tr>
              <th>Page</th>
              <th>Type</th>
            </tr>
          </tbody>
          {rows}
        </table>
        """

        change_row_templ = """
        <tr>
          <td>
            <ac:link><ri:page ri:content-title="{content_title}" />
            </ac:link>
          </td>
          <td>
            {link}
          </td>
        </tr>
        """

        link_to_change_templ = '<a href="{url}/pages/diffpagesbyversion.action?' + \
                               'pageId={page_id}&amp;selectedPageVersions={curr}&amp;' + \
                               'selectedPageVersions={prev}">changed</a>'

        html.append("<h2>Edits</h2>")
        change_rows = []
        for key in sorted(report.keys()):
            for item in report[key]:
                # TODO: Ignore Version pages in a better way
                if not item["title"].startswith("Version "):
                    curr = int(item["version"])
                    prev = curr - 1  # TODO
                    if key == "changed":
                        link = link_to_change_templ.format(
                            url=url, page_id=item["id"], curr=curr, prev=prev)
                    else:
                        link = key

                    change_rows.append(change_row_templ.format(
                        content_title=item["title"],
                        link=link))

        change_rows_str = "".join(change_rows)
        html.append(change_table_templ.format(rows=change_rows_str))

        return "".join(html)
