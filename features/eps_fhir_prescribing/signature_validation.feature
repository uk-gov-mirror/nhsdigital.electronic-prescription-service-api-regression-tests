@eps_fhir_prescribing @regression @signature_validation
@allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-4652
Feature: Prescription signature validation on creation

  @skip-sandbox
  Scenario: Valid signature succeeds on prescription creation
    Given I am an authorised prescriber with EPS-FHIR-PRESCRIBING app
    And I successfully prepare and sign a nominated acute prescription
    Then the response indicates a success

  @skip-sandbox
  Scenario: Invalid signature is rejected on prescription creation
    Given prescribing signature validation is enabled for the current environment
    And I am an authorised prescriber with EPS-FHIR-PRESCRIBING app
    And I successfully prepare a nominated acute prescription
    When I sign the prescription with an invalid signature
    Then the response indicates a bad request
    And the response body contains a signature validation error
