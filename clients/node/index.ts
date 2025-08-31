/** Node.js client for Exvora AI API. */

export interface ItineraryRequest {
  trip_context: {
    date_range: {
      start: string;
      end: string;
    };
    day_template: {
      start: string;
      end: string;
      pace: string;
    };
    base_place_id: string;
  };
  preferences: {
    themes: string[];
    avoid_tags: string[];
  };
  constraints: {
    daily_budget_cap: number;
    max_transfer_minutes: number;
  };
  locks: Array<{
    start: string;
    end: string;
    title: string;
  }>;
}

export interface FeedbackRequest {
  date: string;
  day_template: {
    start: string;
    end: string;
    pace: string;
  };
  trip_context: {
    base_place_id: string;
  };
  preferences: {
    themes: string[];
    avoid_tags: string[];
  };
  constraints: {
    daily_budget_cap: number;
    max_transfer_minutes: number;
  };
  locks: Array<{
    start: string;
    end: string;
    title: string;
  }>;
  actions: Array<{
    type: string;
    place_id?: string;
    rating?: number;
  }>;
}

export class ExvoraClient {
  private baseUrl: string;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl;
  }

  async buildItinerary(requestData: ItineraryRequest): Promise<any> {
    const response = await fetch(`${this.baseUrl}/v1/itinerary`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async feedback(requestData: FeedbackRequest): Promise<any> {
    const response = await fetch(`${this.baseUrl}/v1/itinerary/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }
}

// Convenience functions
export async function buildItinerary(
  requestData: ItineraryRequest, 
  baseUrl: string = "http://localhost:8000"
): Promise<any> {
  const client = new ExvoraClient(baseUrl);
  return client.buildItinerary(requestData);
}

export async function feedback(
  requestData: FeedbackRequest, 
  baseUrl: string = "http://localhost:8000"
): Promise<any> {
  const client = new ExvoraClient(baseUrl);
  return client.feedback(requestData);
}
