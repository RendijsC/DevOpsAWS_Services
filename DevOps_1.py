import boto3
import random
import string
import requests
import webbrowser
import json
import time
import subprocess

KeyName = 'DevOpsAssKey'
#Instances

try:
# Creates ec2 instance
    ec2 = boto3.resource('ec2')
    new_instances = ec2.create_instances(
    	#Instance configuration
        ImageId='ami-0bb4c991fa89d4b9b', 
        MinCount=1,
        MaxCount=1,
        InstanceType='t2.nano',
        KeyName= KeyName,
        SecurityGroupIds=['sg-09201911f3cdc84e6'],
        #creates apache server and creates Html file displaying data
        UserData="""#!/bin/bash
            yum install httpd -y
            systemctl enable httpd
            systemctl start httpd
            echo '<html>' > index.html
            echo '<h1>Instance MetaData </h1>' >> index.html
            echo '<b>Instance ID:</b> ' >> index.html
            curl http://169.254.169.254/latest/meta-data/instance-id >> index.html
            echo '<br>' >> index.html
            echo '<b>Instance Type:</b> ' >> index.html
            curl http://169.254.169.254/latest/meta-data/instance-type >> index.html
            echo '<br>' >> index.html
            echo '<b>Availability Zone:</b> ' >> index.html
            curl http://169.254.169.254/latest/meta-data/placement/availability-zone >> index.html
            
            cp index.html /var/www/html/index.html
            """,
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': 'Web server'
                    },
                ]
            },
        ],
    )
    InstanceID = new_instances[0].id,
    print(f"Instance '{InstanceID}' created successfully")
   

except Exception as e:
    print("Error occurred making instnace ec2: ", e)



# Creating Buckets
#generates random name
random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
BucketName = f'{random_chars}-cielava'


try:
	#create bucket
	s3 = boto3.resource("s3")
	new_bucket = s3.create_bucket(Bucket=BucketName)


	s3 = boto3.client("s3")
	#puts image in bucket
	image_response = requests.get('http://devops.witdemo.net/logo.jpg') #gets image from the URL
	image_key = 'logo.jpg' #sets image from website
	s3.put_object(Body=image_response.content, Bucket=BucketName, Key=image_key, ContentType = "image/jpg")#puts image into bucket
	#puts image from s3 bucket into html page 
	html_content = f'<html><body><h1>My S3 Bucket</h1><img src="http://{BucketName}.s3-website-us-east-1.amazonaws.com/logo.jpg" alt="Logo"></body></html>'
	# puts index into bucket
	html_key = 'index.html'
	s3.put_object(Body=html_content, Bucket=BucketName, Key=html_key, ContentType = "text/html")

	print(f"Bucket '{BucketName}' created successfully. Image and HTML file uploaded.")
	
except Exception as e:
	print("Error occurred making bucket", e)



#make Bucket public
s3.delete_public_access_block(Bucket=BucketName)   # delete bucket access block

bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": f"arn:aws:s3:::{BucketName}/*"
                }
                ]
}
s3.put_bucket_policy(Bucket=BucketName,Policy=json.dumps(bucket_policy))

s3 = boto3.resource('s3')

website_configuration = {
 'ErrorDocument': {'Key': 'error.html'},
 'IndexDocument': {'Suffix': 'index.html'},
}

bucket_website = s3.BucketWebsite(BucketName) 

response = bucket_website.put(WebsiteConfiguration=website_configuration)


#Automatically go to website
new_instances[0].wait_until_running()
new_instances[0].reload() # to reload the instance to get ip address

ec2_ip = new_instances[0].public_ip_address
s3_url = f'http://{BucketName}.s3-website-us-east-1.amazonaws.com'

time.sleep(60)
webbrowser.open_new_tab(f'http://{ec2_ip}')
webbrowser.open_new_tab(s3_url)

#save text file https://www.pythontutorial.net/python-basics/python-create-text-file/
with open('rcielava-website.txt', 'w') as f:
    f.write(f'http://{ec2_ip}')
    f.write(f'http://{BucketName}.s3-website-us-east-1.amazonaws.com')


#monitoring
try:
	cmd1 = f"scp -o StrictHostKeyChecking=no -i {KeyName}.pem monitoring.sh ec2-user@{ec2_ip}:."
	cmd2 = f"ssh -o StrictHostKeyChecking=no -i {KeyName}.pem ec2-user@{ec2_ip} 'chmod 700 monitoring.sh'"
	cmd3 = f"ssh -o StrictHostKeyChecking=no -i {KeyName}.pem ec2-user@{ec2_ip} './monitoring.sh'"
	result1 = subprocess.run(cmd1, shell=True)
	result2 = subprocess.run(cmd2, shell=True)
	result3 = subprocess.run(cmd3, shell=True)
	print("Monitoring was succesful on instance")
except Exception as e:
	print("Error occured while running monitoring on instance",e)


#additional functions Simple Notification system SNS
#https://www.learnaws.org/2021/05/05/aws-sns-boto3-guide/ reference
try:
    # Create SNS client
    sns = boto3.client('sns', region_name='us-east-1')
    
    # email and topic name
    email = 'cielavarendijs8@gmail.com'
    name = 'DevOps'
    
    # Create SNS topic
    topic = sns.create_topic(Name=name)
    
    # Subscribe to the topic
    subscription = sns.subscribe(Protocol='email', Endpoint=email, TopicArn=topic['TopicArn'])
   
    instance_info = {
        "EC2 Instance Type": new_instances[0].instance_type,
        "EC2 ID": new_instances[0].id,
        "EC2 IP": ec2_ip,
        "URL to s3 bucket": s3_url
    }
    
    # Publish the instance information to the SNS topic
    sns.publish(
        TopicArn=topic['TopicArn'],
        Message=json.dumps(instance_info),
        Subject='EC2 Instance Information'
    )
    print("Instance information published to SNS topic successfully and you have been invited to join the topic on your email")

except Exception as e:
    print("An error occurred when sending SNS: ", e)



