@eps_fhir @claim @regression @blocker @smoke
Feature: I can claim for dispensed prescriptions

  @allure.tms:https://nhsd-jira.digital.nhs.uk/browse/AEA-5963
  Scenario Outline: I can claim for a prescription
    Given a <Nomination> <Type> prescription has been created, released and dispensed using apim apis
    When I submit a claim for the prescription
    Then the response indicates a success
    And the response body indicates a successful claim
    Examples:
      | Nomination    | Type   | Variation           |
      | nominated     | acute  |                     |
      | non-nominated | acute  |                     |
      | nominated     | repeat |                     |
      | non-nominated | repeat |                     |
      | nominated     | eRD    |                     |
      | non-nominated | eRD    |                     |
      | nominated     | eRD    | repeat_in_subDetail |
      | non-nominated | eRD    | repeat_in_subDetail |

  @negative
  Scenario Outline: I cannot claim for a prescription that has not been dispensed
    Given a <Nomination> <Type> prescription has been created and released using apim apis
    When I submit a claim for the prescription
    Then the response indicates a bad request
    And the response body returns "error": "PRESCRIPTION_INVALID_STATE_TRANSITION"
    Examples:
      | Nomination    | Type   |
      | nominated     | acute  |
      | non-nominated | acute  |
      | nominated     | repeat |
      | non-nominated | repeat |
      | nominated     | eRD    |
      | non-nominated | eRD    |
