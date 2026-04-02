@eps_fhir_dispensing @regression @blocker @smoke
@allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-4432
Feature: I can dispense prescriptions

  @dispense
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-4941
  Scenario Outline: I can dispense a prescription
    Given a <Nomination> <Type> prescription has been created and released using proxygen apis
    When I dispense the prescription
    Then the response indicates a success
    And the response body indicates a successful dispense action
    Examples:
      | Nomination    | Type   |
      | nominated     | acute  |
      | non-nominated | acute  |
      | nominated     | repeat |
      | non-nominated | repeat |
      | nominated     | eRD    |
      | non-nominated | eRD    |

  @release
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-6543
  Scenario: The $release endpoint can be accessed with user-restricted auth when a practitioner role is given
    Given a nominated acute prescription has been created using proxygen apis
    And I am an authorised dispenser with EPS-FHIR-DISPENSING app
    When I release the prescription
    Then the response indicates a success
    And the response body indicates a successful release action

  @release @application-restricted
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-6543
  Scenario: The $release endpoint cannot be accessed with application-restricted JWT auth
    Given a nominated acute prescription has been created using proxygen apis
    And I am an authorised dispenser with EPS-FHIR-DISPENSING-JWT app
    When I try to release the prescription
    Then the response indicates forbidden

  @release
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-6543
  Scenario: The $release endpoint rejects requests that do not contain a practitioner role
    Given a nominated acute prescription has been created using proxygen apis
    And I am an authorised dispenser with EPS-FHIR-DISPENSING app
    When I try to release the prescription without a practitioner role
    Then the response indicates a bad request

  @release-unattended @application-restricted
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-6543
  Scenario: The $release-unattended endpoint can be accessed with JWT auth when the practitioner role is omitted
    Given a nominated acute prescription has been created using proxygen apis
    And I am an authorised dispenser with EPS-FHIR-DISPENSING-JWT app
    When I release the prescription via the unattended endpoint
    Then the response indicates a success
    And the response body indicates a successful release action

  @release-unattended
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-6543
  Scenario: The $release-unattended endpoint cannot be accessed with user-restricted auth
    Given a nominated acute prescription has been created using proxygen apis
    And I am an authorised dispenser with EPS-FHIR-DISPENSING app
    When I try to release the prescription via the unattended endpoint
    Then the response indicates forbidden

  @release-unattended @application-restricted
  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-6543
  Scenario: The $release-unattended endpoint rejects requests that contain a practitioner role
    Given a nominated acute prescription has been created using proxygen apis
    And I am an authorised dispenser with EPS-FHIR-DISPENSING-JWT app
    When I try to release the prescription via the unattended endpoint with a practitioner role
    Then the response indicates a bad request

  @amend
  Scenario: I can amend a single dispense notification
    Given a new prescription has been dispensed using proxygen apis
    When I amend the dispense notification
    Then the response indicates a success
    And the response body indicates a successful amend dispense action

  @withdraw
  Scenario: I can withdraw a dispense notification
    Given a new prescription has been dispensed using proxygen apis
    When I withdraw the dispense notification
    Then the response indicates a success
    And the response body indicates a successful dispense withdrawal action
