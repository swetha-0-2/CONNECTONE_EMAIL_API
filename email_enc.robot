*** Settings ***
Library    ./email_enc.py
Library    DataDriver    file=api_email_enc.xlsx    encoding=utf-8    dialect=xlsx

Test Template    Execute APIs

*** Test Cases ***
${test_case_id}-${test_desc}
    [Template]    Execute API   ${test_case_id}    ${test_desc}    ${url}    ${payload}    ${expected_response}

*** Keywords ***
Execute APIs
    [Arguments]    ${test_case_id}    ${test_desc}    ${url}    ${payload}    ${expected_response}
    ${result}=    Execute_Api    ${test_case_id}    ${test_desc}    ${url}    ${payload}    ${expected_response}
    Run Keyword If    '${result}' == 'Fail'    Fail    Test case failed for ${test_case_id} - ${test_desc}


