@psu @regression
@allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-4222
Feature: I can send an update to PSU

  @skip-sandbox @e2e @blocker @smoke @post-dated @post-dated-not-ready
  Scenario: I can send 'With Pharmacy' then a post-dated 'Ready to Collect' update and see prescription 'With Pharmacy'
    Given I am an authorised prescriber with EPS-FHIR-PRESCRIBING app
    And I successfully prepare and sign a prescription
    And I am authorised to send prescription updates
    When I send a 'With Pharmacy' update
    And I send a 'Ready to Collect' post-dated update
    Then '1' updates are returned from get-status-updates endpoint
    Then the prescription item has a coding of 'With Pharmacy' with a status of 'in-progress'

  @skip-sandbox @e2e @blocker @smoke @post-dated @post-dated-ready
  Scenario: I can send 'With Pharmacy' then a post-dated 'Ready to Collect', advance clock and see prescription 'Ready to Collect'
    Given I am an authorised prescriber with EPS-FHIR-PRESCRIBING app
    And I successfully prepare and sign a prescription
    And I am authorised to send prescription updates
    When I send a 'With Pharmacy' update
    And I send a 'Ready to Collect' post-dated update
    And I advance the clock to beyond the post-dated time
    Then '2' updates are returned from get-status-updates endpoint
    Then the prescription item has a coding of 'Ready to Collect' with a status of 'in-progress'

  @skip-sandbox @e2e @blocker @smoke @post-dated @post-dated-revoked
  Scenario: I can send updates: 'With Pharmacy', post-dated 'Ready to Collect' and 'With Pharmacy' update and see prescription 'With Pharmacy'
    Given I am an authorised prescriber with EPS-FHIR-PRESCRIBING app
    And I successfully prepare and sign a prescription
    And I am authorised to send prescription updates
    When I send a 'With Pharmacy' update
    And I send a 'Ready to Collect' post-dated update
    And I advance the clock to beyond the post-dated time
    And I send a 'With Pharmacy' update
    Then '1' updates are returned from get-status-updates endpoint
    Then the prescription item has a coding of 'With Pharmacy' with a status of 'in-progress'
