import matplotlib.pyplot as plt

def plot_covid_deaths(incidence_summary):
    plt.plot(incidence_summary['Year'], incidence_summary['COVID-19 Deaths'], marker='o')
    plt.title('Yearly COVID-19 Mortality')
    plt.xlabel('Year')
    plt.ylabel('COVID-19 Deaths')
    plt.grid(True)
    plt.show()
