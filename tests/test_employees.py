from io import BytesIO

import pytest

Workbook = pytest.importorskip("openpyxl").Workbook

from components.employees import import_employees


def _workbook(rows):
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    return content.getvalue()


def test_import_employee_records():
    content = _workbook([
        ["Name", "Role", "Experience Years", "Skills", "ID"],
        ["Alex Rivera", "Backend dev", 4.5, "Python, SQL", "123"],
        [None, None, None, None, None],
        ["Sam Chen", "QA", None, None, None],
    ])
    employees = import_employees(content)
    assert len(employees) == 2
    assert employees["excel-123"]["skills"] == ["Python", "SQL"]
    assert employees["excel-123"]["experience_years"] == 4.5
    assert import_employees(content) == employees


@pytest.mark.parametrize("rows, message", [
    ([["Role"], ["QA"]], "name column"),
    ([["Name", "Role"], [None, "QA"]], "name is required"),
    ([["Name", "Experience Years"], ["Alex", -1]], "non-negative"),
    ([["Name", "Experience Years"], ["Alex", "invalid"]], "non-negative"),
    ([["Name"], ["Alex"], ["Alex"]], "duplicate employee"),
    ([["Name"]], "no employee"),
])
def test_invalid_employee_workbook(rows, message):
    with pytest.raises(ValueError, match=message):
        import_employees(_workbook(rows))


def test_invalid_file():
    with pytest.raises(ValueError, match="Excel workbook"):
        import_employees(b"not a workbook")