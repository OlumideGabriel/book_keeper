document.getElementById('recommend-button').addEventListener('click', function() {
    const button = this;
    button.classList.add('loading');

    // Simulate loading for 2 seconds
    setTimeout(() => {
      button.classList.remove('loading');
      // Replace with actual recommendation generation logic
      alert('Recommendations generated!');
    }, 2000);
  });