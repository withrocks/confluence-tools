
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
              <th>Change</th>
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
            <a href="{url}/pages/diffpagesbyversion.action?pageId={page_id}&amp;selectedPageVersions={curr}&amp;selectedPageVersions={prev}"> diff v{prev}..v{curr} </a>
          </td>
        </tr>
        """

        html.append(version_table)
        html.append("<h2>Changed</h2>")
        change_rows = []
        for item in report["changed"]:
            change_rows.append(change_row_templ.format(
                content_title=item["title"],
                url=url,
                curr=2, prev=1, page_id=item["id"]))
        change_rows_str = "".join(change_rows)
        html.append(change_table_templ.format(rows=change_rows_str))

        """
        html.append("<h2>Added</h2>")
        for item in report["new"]:
            html.append("<p>{}</p>".format(item["title"]))
        """

        return "".join(html)
